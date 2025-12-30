"""渐进式锁定验证器 - 引导 LLM 逐步收敛到正确结果"""
# pylint: disable=protected-access  # Intentional access to _ValidationContext internals

from xml.etree.ElementTree import Element

from .const import ID_KEY
from .format import _ValidationContext


class ProgressiveLockingValidator:
    """
    渐进式锁定验证器：
    - 验证时收集所有错误（包括已锁定区域）
    - 识别无错误的子树并锁定
    - 只报告未锁定区域的错误
    - 保证收敛：每轮至少锁定一个节点，最多 N 轮完成
    """

    def __init__(self):
        self.locked_ids: set[int] = set()
        self.no_progress_count: int = 0
        self.lock_history: list[set[int]] = []  # 记录每轮锁定的节点

    def validate_with_locking(
        self,
        template_ele: Element,
        validated_ele: Element,
        errors_limit: int,
    ) -> tuple[bool, str | None, set[int]]:
        """
        使用渐进式锁定进行验证

        返回：
        - is_complete: 是否所有节点都已锁定（完成）
        - error_message: 未锁定区域的错误消息（None 表示无错误）
        - newly_locked: 本轮新锁定的节点 ID 集合
        """

        # 1. 执行完整验证（包括已锁定区域）
        context = _ValidationContext()
        context.validate(raw_ele=template_ele, validated_ele=validated_ele)

        # 2. 获取所有错误（以路径为 key）
        all_errors = context._errors

        # 3. 识别可以新锁定的节点
        newly_locked = self._find_lockable_nodes(template_ele, validated_ele, all_errors)

        # 4. 检测卡住情况并解锁
        if not newly_locked and self.locked_ids:
            self.no_progress_count += 1
            if self.no_progress_count >= 3:
                # 卡住了，解锁最近的 2 个节点重试
                self._unlock_recent(count=2)
                self.no_progress_count = 0
        else:
            self.no_progress_count = 0

        # 5. 更新锁定集合
        self.locked_ids.update(newly_locked)
        self.lock_history.append(newly_locked.copy())

        # 6. 过滤错误：只保留未锁定区域的错误
        unlocked_errors = self._filter_unlocked_errors(all_errors)

        # 7. 生成错误消息
        error_message = self._format_errors(unlocked_errors, errors_limit, template_ele)

        # 8. 检查是否完成
        total_nodes = self._count_nodes_with_id(template_ele)
        is_complete = len(self.locked_ids) == total_nodes and error_message is None

        return is_complete, error_message, newly_locked

    def _find_lockable_nodes(
        self, template_ele: Element, validated_ele: Element, errors: dict[tuple[int, ...], list[str]]
    ) -> set[int]:
        """
        找到可以锁定的节点（该节点及所有后代都无错误，且尚未锁定）

        策略：自底向上，优先锁定叶子节点
        """
        lockable = set()

        # 收集所有带 id 的节点，按深度排序（深度优先）
        nodes_with_depth = []
        for elem in template_ele.iter():
            elem_id_str = elem.get(ID_KEY)
            if elem_id_str is not None:
                elem_id = int(elem_id_str)
                if elem_id not in self.locked_ids:
                    depth = self._get_depth(elem, template_ele)
                    nodes_with_depth.append((depth, elem_id, elem))

        # 从最深的节点开始检查
        nodes_with_depth.sort(reverse=True, key=lambda x: x[0])

        for depth, elem_id, elem in nodes_with_depth:
            # 检查该节点的子树是否完全无错误
            if self._subtree_is_error_free(elem, template_ele, errors):
                # 验证在 validated_ele 中也存在对应节点
                validated_node = self._find_by_id(validated_ele, elem_id)
                if validated_node is not None:
                    lockable.add(elem_id)

        return lockable

    def _subtree_is_error_free(
        self, root: Element, template_root: Element, errors: dict[tuple[int, ...], list[str]]
    ) -> bool:
        """检查子树是否完全无错误"""

        # 获取该节点在 template 中的路径
        root_path = self._get_path_to_node(root, template_root)
        if root_path is None:
            return False

        # 检查该路径及其所有后代路径是否有错误
        for error_path in errors.keys():
            # 如果错误路径是 root_path 的后代或等于 root_path
            if self._is_descendant_path(error_path, root_path):
                return False

        return True

    def _get_path_to_node(self, target: Element, root: Element) -> tuple[int, ...] | None:
        """获取从 root 到 target 的路径（以 id 序列表示）"""

        def find_path(current: Element, path: list[int]) -> list[int] | None:
            if current is target:
                return path

            current_id_str = current.get(ID_KEY)
            if current_id_str is not None:
                current_path = path + [int(current_id_str)]
            else:
                current_path = path

            for child in current:
                result = find_path(child, current_path)
                if result is not None:
                    return result

            return None

        path = find_path(root, [])
        return tuple(path) if path is not None else None

    def _is_descendant_path(self, path: tuple[int, ...], ancestor_path: tuple[int, ...]) -> bool:
        """检查 path 是否是 ancestor_path 的后代或相等"""
        if len(path) < len(ancestor_path):
            return False
        return path[: len(ancestor_path)] == ancestor_path

    def _get_depth(self, elem: Element, root: Element) -> int:
        """获取元素的深度"""
        path = self._get_path_to_node(elem, root)
        return len(path) if path else 0

    def _find_by_id(self, root: Element, target_id: int) -> Element | None:
        """在树中查找指定 id 的元素"""
        for elem in root.iter():
            elem_id_str = elem.get(ID_KEY)
            if elem_id_str is not None and int(elem_id_str) == target_id:
                return elem
        return None

    def _filter_unlocked_errors(self, errors: dict[tuple[int, ...], list[str]]) -> dict[tuple[int, ...], list[str]]:
        """过滤错误：只保留路径中包含未锁定节点的错误"""
        unlocked_errors = {}

        for path, error_list in errors.items():
            # 检查路径中是否有未锁定的节点
            has_unlocked = any(node_id not in self.locked_ids for node_id in path)
            if has_unlocked:
                unlocked_errors[path] = error_list

        return unlocked_errors

    def _format_errors(
        self, errors: dict[tuple[int, ...], list[str]], limit: int, template_ele: Element
    ) -> str | None:
        """格式化错误消息（复用现有逻辑）"""
        if not errors:
            return None

        # 使用现有的错误格式化逻辑
        context = _ValidationContext()
        context._errors = errors

        # 构造 _tag_text_dict，从 template_ele 中提取真实的标签信息
        id_to_elem: dict[int, Element] = {}
        for elem in template_ele.iter():
            elem_id_str = elem.get(ID_KEY)
            if elem_id_str is not None:
                elem_id = int(elem_id_str)
                id_to_elem[elem_id] = elem

        # 填充 _tag_text_dict
        for path in errors.keys():
            for node_id in path:
                if node_id not in context._tag_text_dict:
                    elem = id_to_elem.get(node_id)
                    if elem is not None:
                        context._tag_text_dict[node_id] = self._str_tag(elem)
                    else:
                        context._tag_text_dict[node_id] = f'<tag id="{node_id}">'

        return context.errors(limit=limit)

    def _str_tag(self, ele: Element) -> str:
        """生成标签的字符串表示（与 format.py 中的逻辑一致）"""
        ele_id = ele.get(ID_KEY)
        content: str
        if ele_id is not None:
            content = f'<{ele.tag} id="{ele_id}"'
        else:
            content = f"<{ele.tag}"
        if len(ele) > 0:
            content += f"> ... </{ele.tag}>"
        else:
            content += " />"
        return content

    def _count_nodes_with_id(self, root: Element) -> int:
        """统计带有 id 属性的节点数量"""
        count = 0
        for elem in root.iter():
            if elem.get(ID_KEY) is not None:
                count += 1
        return count

    def _unlock_recent(self, count: int):
        """解锁最近锁定的 count 个节点"""
        if not self.lock_history:
            return

        unlocked_count = 0
        # 从最近的历史记录开始解锁
        for i in range(len(self.lock_history) - 1, -1, -1):
            if unlocked_count >= count:
                break

            locked_in_round = self.lock_history[i]
            for node_id in locked_in_round:
                if unlocked_count >= count:
                    break
                if node_id in self.locked_ids:
                    self.locked_ids.remove(node_id)
                    unlocked_count += 1

    def get_progress_summary(self, total_nodes: int) -> str:
        """获取进度摘要"""
        locked_count = len(self.locked_ids)
        percentage = (locked_count / total_nodes * 100) if total_nodes > 0 else 0
        return f"{locked_count}/{total_nodes} nodes locked ({percentage:.1f}%)"
