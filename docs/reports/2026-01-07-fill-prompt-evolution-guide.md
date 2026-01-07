# Fill Stage Prompt 演进指南 (Version 1-6)

**日期**: 2026-01-07
**测试范围**: Newton's philosophical analysis of space and time（截止点）
**核心文件**: `epub_translator/data/fill.jinja`

---

## 执行摘要

本文档记录了 fill.jinja prompt 从 Version 1 到 Version 6 的演进过程，重点分析哪些 prompt 内容是**关键不可删除**的，哪些新增内容解决了什么问题。这是今后调整 prompt 的重要参考。

**最终推荐**: Version 6 (Error Type 7 + 温度递增机制)

---

## 版本对比概览（新口径：段落去重）

| 版本 | 最终失败段落 | 出错段落总数 | 需要 Retry 2+ | Prompt 关键变化 |
|------|-------------|-------------|--------------|----------------|
| Version 1 | 0 ✅ | 10 | 0 | 基线版本（210行） |
| Version 2 | 1 ❌ | 8 | 1 | 移除 data-orig-len 相关描述 |
| Version 3 | 1 ❌ | 9 | 3 | 移除 Source text 相关描述 |
| Version 4 | 1 ❌ | 5 | 2 | 恢复完整 prompt + 降温到 0.2 |
| Version 5 | 1 ❌ | 6 | 1 | 加入温度递增（prompt 不变）|
| Version 6 | 0 ✅ | 12 | 6 | **新增 Error Type 7** |

**关键发现**: Version 1 的 210 行 prompt 中，几乎所有内容都是必要的。

---

## 一、Prompt 的核心架构（不可删除）

### 1.1 CRITICAL RULES 区域（Lines 5-26）

**作用**: 建立 AI 的基本认知框架

```jinja
IMPORTANT: Translation fluency is SECONDARY to structure preservation.
If the translated text flows naturally but doesn't match template structure,
you MUST break the flow to insert required tags.
```

**关键性**: ⭐⭐⭐⭐⭐ 必须保留

**教训**:
- 这段话在 Version 4/5 中被证明**至关重要**
- 没有这段，AI 会优先保持翻译的流畅性，而忽略 XML 结构
- "fluency is SECONDARY" 必须明确写出，不能暗示

---

### 1.2 ID Handling 说明（Lines 16-19）

```jinja
2. ID Handling:
   - Tags WITH id="X": Disambiguation markers for structurally similar elements
   - Tags WITHOUT id: Structurally unique, match by position and tag name
   - NEVER add, remove, or change id attributes
```

**关键性**: ⭐⭐⭐⭐⭐ 必须保留

**教训**:
- "Disambiguation markers" 这个定位非常关键
- 告诉 AI: id 不是所有元素都有，只有需要消歧的才有
- Version 1-6 都保留了这段，没有尝试删除

---

### 1.3 SEMANTIC matching 强调（Line 26）

```jinja
IMPORTANT: Translation may change word order - use SEMANTIC matching, not position
```

**关键性**: ⭐⭐⭐⭐⭐ 必须保留

**教训**:
- 这是解决跨语言词序变化的核心原则
- 但仅有这句话**不够**，需要配合 Error Type 6 和 Error Type 7 的具体案例

---

## 二、Error Types 区域（不可删减）

### 2.1 Error Type 1-5（Lines 32-54）

**作用**: 定义基础错误类型

**关键性**: ⭐⭐⭐⭐⭐ 必须保留

**教训**:
- Version 1 中有简化版的 Special Cases 1-5（后来被删除）
- 但 Error Type 1-5 **从未尝试删除**
- 每个 Error Type 都有实际对应的验证错误

**特别注意**: Error Type 2 (Tag count mismatch) 必须有具体例子：
```jinja
Example template:
<p id="1">
  <span>text1</span>
  <span>text2</span>
</p>

❌ WRONG: <p id="1"><span>merged text</span></p>  (only 1 span, expected 2)
✓ CORRECT: <p id="1"><span>text1</span><span>text2</span></p>
```

---

### 2.2 Error Type 6（Lines 56-71）

**作用**: 处理词序变化时的语义匹配

**关键性**: ⭐⭐⭐⭐⭐ 必须保留

**两个例子的作用**:

**Example 1**: 词序完全颠倒
```jinja
Template: "reviewer of <span id="5">Book</span> in <span id="6">Journal</span>"
Translation: "Journal 上对 Book 的评论者"
```
- 教会 AI: Journal 虽然在前面，但要 wrap id="6"（不是 id="5"）

**Example 2**: 打破流畅性以保持结构
```jinja
Template: "published in <span id="5">Book Title</span> in 1990"
Translation: "于1990年出版的《书名》" (flows naturally, but loses structure)

✓ CORRECT: 于1990年出版的<span id="5">《书名》</span>
```
- 强化 "fluency is SECONDARY" 的原则
- 给出具体的"打破流畅"案例

**教训**: Example 2 在 Version 4/5 中被证明**非常重要**，不能删除。

---

### 2.3 Error Type 7（Lines 73-100）⭐ Version 6 新增

**作用**: 解决 Version 2-5 的死循环问题（p#2 Principia + 1687）

**关键性**: ⭐⭐⭐⭐⭐ 解决了致命问题

**问题背景**:
```
Template: "<span id="3">Principia</span> in <span id="4"><a>1687</a></span>"
Translation: "《自然哲学的数学原理》于1687年出版"

Version 2-5 的错误:
AI 认为 id="3" 应该 wrap "1687"（因为紧跟在"于"后面）
→ 导致 id="5" 找不到 → Retry 5 次都重复相同错误 → max retry
```

**解决方案**:
```jinja
Error Type 7: Adjacent elements with different semantic types
CRITICAL: When template has adjacent elements of DIFFERENT semantic types
(book title + year, person name + date, place + number, etc.),
you MUST match by SEMANTIC TYPE, NOT by position in translated text.

Example 1: Book title and year adjacent
Template: "<span id="3">Book Title</span> in <span id="4"><a>1990</a></span>"
Translation: "《书名》于1990年出版"

❌ WRONG: 《书名》于<span id="3">1990</span>年出版
  (Matching by position: "1990" appears after "于", so wrapping it with id="3")
  (This is WRONG because you matched a YEAR to a template that expects a BOOK TITLE)

✓ CORRECT: <span id="3">《书名》</span>于<span id="4"><a>1990</a></span>年出版
  (Matching by SEMANTIC TYPE: book title → book title, year → year)
```

**关键设计**:
1. **用通用占位符** (`Book Title`, `《书名》`)，不用具体书名 (`Principia`)
   - 避免 AI 过拟合特定案例

2. **明确指出错误的推理过程**:
   ```
   (Matching by position: "1990" appears after "于", so wrapping it with id="3")
   ```
   - 直接揭示 AI 的错误逻辑

3. **强调语义类型**:
   ```
   This is WRONG because you matched a YEAR to a template that expects a BOOK TITLE
   ```

4. **辅助线索**:
   ```jinja
   - data-orig-len can help: book titles usually have longer token counts than years
   - Years are typically 4-digit numbers (1687, 1990, 2024, etc.) - easy to identify
   ```

**测试结果**:
- Version 6: 0 个 max retry ✅
- p#2 的 Principia 问题完全解决

**副作用**:
- 出错段落从 10 个增加到 12 个（+20%）
- 可能让 AI 在第一次尝试时更谨慎（宁可漏掉，不要 wrap 错）
- 但所有错误都在 Retry 2 内解决，没有死循环

---

## 三、STEP-BY-STEP 区域（Lines 103-107）

**作用**: 提供操作性指导（不是理论）

**关键性**: ⭐⭐⭐⭐⭐ 必须保留

**教训**:
- Version 1 的简化尝试中，删除 STEP-BY-STEP 后立即出现大量错误
- STEP-BY-STEP 包含的不是理论，而是**操作步骤**:
  - Step 1: 数元素
  - Step 2: 看 Source 如何映射
  - Step 3: 应用到 Translation
  - Step 4: 验证

**特别重要的部分**:
```jinja
Step 3: Apply to Translation
- For inline elements WITH id attributes:
  * Locate the SEMANTIC equivalent in translated text
  * Wrap it with the SAME tag and id, even if position changed
  * Example: <span id="5">Book</span> in "reviewer of Book in Journal"
    becomes <span id="5">书</span> in "Journal 上对书的评论者" (position changed!)
```

这个例子和 Error Type 6 Example 1 **互相呼应**，强化语义匹配原则。

---

## 四、Special Cases 区域

### 4.1 Special Case 1: data-orig-len（Lines 112-117）

**作用**: 解释 data-orig-len 的含义和用法

```jinja
Template: <span id="5" data-orig-len="42">text</span>
→ The data-orig-len shows token count of ORIGINAL text
→ Use as HINT for locating element, not strict constraint
→ Translation length may differ significantly across languages
→ Focus on semantic matching, not length matching
```

**关键性**: ⭐⭐⭐⭐ 重要

**教训**:
- Version 2 移除 data-orig-len 后，出现死循环（8 个出错段落 + 1 个失败）
- Version 3 同时移除 Source + data-orig-len 后，更差（9 个出错段落 + 1 个失败）
- **必须强调**: "Use as HINT", "not strict constraint"
  - 否则 AI 会过度关注长度匹配，忽略语义匹配

---

### 4.2 Special Case 2: Fallback Strategy（Lines 119-151）

**作用**: 当翻译简化/省略源内容时的处理策略

```jinja
When Translation Simplifies or Omits Source Elements

Example scenario:
- Template: <span id="1">Latin Name</span>, or <span id="2">English Translation</span>
- Translation: 中文名称 (merged both into one concept, no "or" connector)

CORRECT approach (in priority order):
1. FIRST: Exhaust semantic matching
2. IF genuinely no match exists:
   - Use source text as fallback: <span id="2">English Translation</span>
   - Place it in a natural position
3. Mixed language output is ACCEPTABLE
```

**关键性**: ⭐⭐⭐⭐ 重要

**教训**:
- 这个 Special Case 在 Version 1-6 都保留
- "Mixed language output is ACCEPTABLE" 是关键
- 告诉 AI: 宁可保持结构完整（即使中英混合），也不要丢失元素

---

## 五、关键原则总结

### 5.1 不可删除的内容（经过实验验证）

1. **CRITICAL RULES** - 特别是 "fluency is SECONDARY"
2. **All Error Types (1-7)** - 每个都对应实际错误
3. **STEP-BY-STEP** - 提供操作性指导
4. **Special Case 1 (data-orig-len)** - Version 2 证明了其必要性
5. **Special Case 2 (Fallback)** - 处理翻译简化的情况

### 5.2 新增内容的指导原则

当需要新增 Error Type 时（如 Error Type 7）：

1. **明确指出错误的推理过程**
   ```
   ❌ WRONG: 《书名》于<span id="3">1990</span>年
     (Matching by position: "1990" appears after "于", so wrapping it with id="3")
   ```

2. **使用通用占位符**
   - 不用 "Principia" → 用 "Book Title"
   - 避免过拟合特定案例

3. **给出明确的判断依据**
   ```
   This is WRONG because you matched a YEAR to a template that expects a BOOK TITLE
   ```

4. **提供辅助线索**
   ```
   - data-orig-len can help: book titles usually have longer token counts
   - Years are typically 4-digit numbers (1687, 1990, 2024, etc.)
   ```

5. **保持例子的对称性**
   - 既要给 WRONG 例子（展示错误逻辑）
   - 也要给 CORRECT 例子（展示正确做法）

---

## 六、温度递增机制（代码层面）

**简述**: Version 5-6 引入了温度递增机制 `temperature=(0.2, 0.9)`

**作用**:
- 第一次尝试: temp=0.2（确定性高）
- 每次 retry: 温度指数增长（0.2 → 0.5 → 0.65 → 0.725...）
- 帮助 AI 跳出死循环

**局限性**:
- Version 5 证明：**温度递增本身无法解决死循环**
- 如果 AI 的理解框架错误，温度再高也没用
- 必须配合 Error Type 7（正确的认知框架）

**最佳实践**:
- 温度递增 + 正确的 prompt = 最优方案
- 温度递增是**保险措施**，不是主要解决方案

---

## 七、未来优化方向

如果需要进一步改进 Version 6：

### 7.1 调整温度起点
```python
temperature=(0.15, 0.9)  # 从 0.15 开始，可能提高第一次成功率
```

### 7.2 优化 Error Type 7 的描述

**当前问题**: Version 6 出错段落增加到 12 个（比 Version 1 多 2 个）

**可能原因**: Error Type 7 让 AI 过度谨慎，第一次尝试时容易漏检

**优化方向**: 在 Error Type 7 中增加"积极匹配"的例子
```jinja
IMPORTANT: Don't be too cautious! If semantic types clearly match, wrap them confidently.
Only use the fallback strategy when genuinely no semantic match exists.
```

### 7.3 分析需要 Retry 2 的段落

Version 6 有 6 个段落需要 Retry 2（其中 5 个是 div#19, #31, #34, #37, #40）

**分析方向**:
- 这些 div 是否有共同的结构特征？
- 是否需要针对 div 元素添加特殊说明？

---

## 八、核心教训

### 8.1 Prompt 不能随意删减

- Version 1 的 210 行 prompt **几乎都是必要的**
- 删除任何一个关键部分（如 data-orig-len, STEP-BY-STEP）都会导致性能下降

### 8.2 具体案例比抽象原则更有效

- 仅说 "use SEMANTIC matching" 不够
- 必须给出具体的 WRONG 和 CORRECT 案例
- Error Type 6 和 7 都证明了这一点

### 8.3 指出错误的推理过程很重要

```jinja
❌ WRONG: 《书名》于<span id="3">1990</span>年
  (Matching by position: "1990" appears after "于")  ← 明确指出 AI 的错误逻辑
```

### 8.4 温度递增是辅助手段

- 不能依赖温度递增解决所有问题
- 必须先有正确的 prompt（认知框架）
- 温度递增是"保险措施"，防止偶发性卡死

### 8.5 副作用是可接受的

- Version 6 出错段落增加 20%，但解决了死循环
- **可靠性 > 效率**
- 0 个最终失败 > 少几次 retry

---

## 附录：版本详细数据

### A.1 所有版本的段落级错误统计

| 版本 | 失败段落 | 出错段落 | Retry 1 | Retry 2 | Retry 3-5 |
|------|---------|---------|---------|---------|-----------|
| V1   | 0       | 10      | 10      | 0       | 0         |
| V2   | 1       | 8       | 7       | 0       | 1         |
| V3   | 1       | 9       | 6       | 1       | 2         |
| V4   | 1       | 5       | 3       | 1       | 1         |
| V5   | 1       | 6       | 5       | 0       | 1         |
| V6   | 0       | 12      | 6       | 6       | 0         |

### A.2 关键段落的命运

**p#2 (Principia + 1687 死循环问题):**

| 版本 | 结果 | 说明 |
|------|------|------|
| V1   | 第一次成功 | 未遇到此问题 |
| V2-5 | Retry 5/5 失败 | 死循环 |
| V6   | 未出现在日志 | 完全解决 |

---

**文档结束**

**关键结论**: Version 6 的 fill.jinja (包含 Error Type 7) + 温度递增机制是当前最优方案。在可靠性相同的前提下（0 失败），以略低的效率换取了更高的鲁棒性和可扩展性。
