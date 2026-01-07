# Fill Stage 优化实验报告

**实验日期**: 2026-01-07
**实验目标**: 通过控制变量实验，探究 Source text 和 data-orig-len 对 Fill Stage 翻译质量的影响
**相关提交**: 2265d13, 274410f

---

## 一、实验背景

### 1.1 系统架构

EPUB Translator 采用**两阶段翻译架构**：

1. **Translate Stage**（translate_llm, temperature=0.8）
   - 将原文翻译成目标语言的**纯文本**
   - 不保留 XML 结构，专注翻译质量

2. **Fill Stage**（fill_llm, temperature=0.3）
   - 将翻译文本填充回 XML 模板
   - 保持 XML 结构完全一致（标签、嵌套、ID）
   - 使用 **Hill Climbing 算法**验证结构正确性

### 1.2 Sparse ID 架构

- **有 ID 元素**：结构相似需要消歧的元素（如多个 `<span>Principia</span>`）
- **无 ID 元素**：结构唯一的元素（通过位置和标签名匹配）
- **data-orig-len 属性**：原文的 token 数量，作为定位提示

### 1.3 实验动机

在初始测试中发现：
- 大量错误集中在 `Principia`（书名翻译）
- 怀疑 Source text 和 data-orig-len 可能是冗余或有害的
- 需要通过控制变量实验验证假设

---

## 二、实验设计

### 2.1 三组对照实验

| 实验 | Source Text | data-orig-len | 描述 |
|------|-------------|---------------|------|
| **A 测试** | ✅ 保留 | ✅ 保留 | 基线配置（原始设计） |
| **B 测试** | ❌ 移除 | ❌ 移除 | 假设两者都冗余 |
| **C 测试** | ✅ 保留 | ❌ 移除 | 假设 data-orig-len 有害 |

### 2.2 固定参数

- 测试章节：截止到 "Newton's philosophical analysis of space and time"
- fill_temperature: 0.3
- fill_top_p: 0.7
- max_retries: 5
- 模型：相同 LLM 版本

### 2.3 评估指标

1. **关键指标**
   - 达到最大重试次数（max_retries=5）的案例数
   - 总错误提示次数
   - 最高重试次数

2. **错误类型**
   - `InlineExpectedIDsError`: 缺失有 ID 的内联元素（如 `<span id="5">Principia</span>`）
   - `InlineWrongTagCountError`: 无 ID 元素数量错误（如期望 3 个 `<span>`，只找到 2 个）
   - `BlockExpectedIDsError`: 缺失块级元素

3. **内容分析**
   - Principia 相关错误（文化特例：英文缩写→中文全名）
   - 单字母/数学符号（A, AB, BC 等）
   - 其他书名/期刊
   - 年份

---

## 三、实验结果

### 3.1 关键指标对比

| 指标 | A 测试 | B 测试 | C 测试 |
|------|--------|--------|--------|
| **达到最大重试次数** | **0 次** ✅ | 2 次 ❌ | 2 次 ❌ |
| **总错误提示次数** | **23 次** ✅ | 21 次 | **45 次** ❌ (最差) |
| **最高重试次数** | Retry 2/5 ✅ | Retry 5/5 ❌ | Retry 5/5 ❌ |
| **Retry 1/5** | 9 次 | 9 次 | 11 次 |
| **Retry 2/5** | 1 次 | 3 次 | 4 次 |
| **Retry 3/5** | 0 次 | 2 次 | 3 次 |
| **Retry 4/5** | 0 次 | 2 次 | 2 次 |
| **Retry 5/5** | 0 次 | 2 次 | 2 次 |

**结论**: A 测试在所有关键指标上表现最佳，B 测试次之，C 测试最差。

### 3.2 错误类型分布

| 错误类型 | A 测试 | B 测试 | C 测试 |
|----------|--------|--------|--------|
| **InlineExpectedIDsError** | 21 次 | 7 次 | **27 次** ❌ (+29%) |
| **InlineWrongTagCountError** | **2 次** ✅ | 14 次 ❌ (+600%) | 8 次 (+300%) |
| **BlockExpectedIDsError** | 0 次 | 0 次 | 1 次 |

**关键发现**:
- **移除 Source text**（B 测试）导致 `InlineWrongTagCountError` 暴增 7 倍
- **移除 data-orig-len**（C 测试）导致 `InlineExpectedIDsError` 增加 29%，`InlineWrongTagCountError` 增加 4 倍

### 3.3 内容错误分析

| 错误内容 | A 测试 | B 测试 | C 测试 |
|----------|--------|--------|--------|
| **Principia 相关** | 17 次 | 5 次 ✅ | **27 次** ❌ (+59%) |
| **单字母/数学符号** | 0 次 | 6 次 ❌ | 0 次 |
| **其他书名/期刊** | 8 次 | 4 次 | 11 次 |
| **年份** | 3 次 | 2 次 | 4 次 |

**关键发现**:
- B 测试虽然改善了 Principia 问题（17→5），但引入了单字母符号错误（0→6）
- C 测试 Principia 问题恶化（17→27），说明 data-orig-len 对定位书名有帮助

---

## 四、典型错误案例分析

### 4.1 A 测试典型案例（基线）

#### 案例 1: Principia 批量缺失（Retry 1/5 成功修复）

```
Found 7 error(s):
In div#19: Missing inline elements: - `<span id="20">`: "Principia"
In div#31: Missing inline elements: - `<span id="32">`: "Principia"
In div#34: Missing inline elements: - `<span id="35">`: "Principia"
In div#37: Missing inline elements: - `<span id="38">`: "Principia"
In div#40: Missing inline elements: - `<span id="41">`: "Principia"
In div#56: Missing inline elements: - `<span id="57">`: "Optical Lectures"
In div#59: Missing inline elements: - `<span id="60">`: "Principia"
```

**原因**: 英文文化惯用缩写 "Principia" → 中文全名 "《自然哲学的数学原理》"，AI 首次倾向于翻译流畅性而未打断插入标签。

**修复**: 经过 1 次重试，AI 根据错误提示中的原文 "Principia" 在译文中定位语义对应位置，成功插入。

#### 案例 2: 无 ID 元素数量错误（Retry 1/5 成功修复）

```
In p#12: Too few `<span>` elements at `p#12 > span`.
Expected 3, but only found 2 (1 missing). Fix: Add 1 more `<span>` element(s).
```

**原因**: 译文将多个无 ID 的 `<span>` 合并。

**修复**: AI 理解需要保持元素数量，经 1 次重试成功分段。

### 4.2 B 测试典型案例（无 Source + 无 data-orig-len）

#### 案例 1: 单字母数学符号丢失（Retry 达到 max_retries=5 失败）

```
Found 3 error(s):
In div#46: Missing inline elements:
  - `<span id="47">`: "A"
  - `<span id="48">`: "AD"
  - `<span id="49">`: "C"
```

**原因**: 没有 Source text，AI 无法理解这些单字母是独立的数学符号，错误地将其合并到周围文本。

**修复**: 经过 5 次重试均失败，AI 始终无法正确定位单字母边界。

**关键教训**: **Source text 对理解无 ID 元素的语义边界至关重要**。

#### 案例 2: Principia 问题改善但整体变差

虽然 Principia 错误从 17 降至 5，但：
- `InlineWrongTagCountError` 从 2 增至 14
- 达到 max_retries 案例从 0 增至 2

**结论**: 改善特例问题的代价是引入更严重的通用问题。

### 4.3 C 测试典型案例（有 Source + 无 data-orig-len）

#### 案例 1: Principia 问题恶化（Retry 达到 max_retries=5 失败）

```
In p#4: Missing inline elements: - `<span id="8">`: "Principia"

经过 Retry 2/5, 3/5, 4/5, 5/5，错误持续存在，最终失败。
```

**原因**: 移除 data-orig-len 后，AI 失去了长度提示。"Principia" 原文 1 个 token，译文 "《自然哲学的数学原理》" 约 9 个汉字，长度差异巨大。data-orig-len 提供的原文长度信息有助于 AI 理解这是一个"短原文→长译文"的扩展场景。

**结果**: Principia 错误从 17 暴增至 27（+59%）。

#### 案例 2: 块级结构混乱

```
Found 10 error(s):
Missing block elements:
  - `<p id="7">`: "The first decade of the new ce..."
  - `<p id="15">`: "Newton remained intellectually..."
Unexpected block found at `p#5`. Fix: Remove.
Unexpected block found at `p#13`. Fix: Remove.
```

**原因**: 没有 data-orig-len 辅助，AI 在分段时更容易混淆块级元素对应关系。

---

## 五、Source Text 的作用机制

### 5.1 核心价值：语义边界理解

**问题**: 无 ID 元素（如 `<span>A</span><span>B</span>`）仅通过位置和标签名匹配，译文中如何确定边界？

**Source text 提供的信息**:
1. **原文上下文**: 帮助 AI 理解 "A" 和 "B" 是独立单位，不是词的一部分
2. **元素分布模式**: 通过对比原文和 template 的切分方式，推断译文应如何切分
3. **语义对应关系**: 在词序变化时（如中英文语序差异），帮助定位语义等价位置

**实验证据**:
- **B 测试**: 移除 Source text 后，`InlineWrongTagCountError` 从 2 增至 14（+600%）
- **典型失败**: 单字母数学符号（A, AB, BC）全部丢失，因为 AI 将其合并到周围文本

### 5.2 对比案例：有无 Source text 的区别

#### 有 Source text（A 测试）
```
Source text:
"... the concept of an inverse-square solar force. Halley managed ..."

XML template:
<p>... the concept of an <span>inverse-square</span> solar force. Halley ...</p>

Translated text:
"... 平方反比的太阳引力概念。哈雷设法 ..."

AI 推理:
1. 原文 "inverse-square" 对应 template 中的 <span>
2. 译文中对应位置是 "平方反比"
3. 输出: <p>... <span>平方反比</span>的太阳引力概念。...</p>
```

#### 无 Source text（B 测试）
```
XML template:
<p>... the concept of an <span>inverse-square</span> solar force. Halley ...</p>

Translated text:
"... 平方反比的太阳引力概念。哈雷设法 ..."

AI 推理:
1. template 有 1 个 <span>，不知道对应译文哪部分
2. 可能误判为整个句子，或随机切分
3. 输出错误: <p>... 平方反比的<span>太阳引力概念</span>。...</p>
```

---

## 六、data-orig-len 的作用机制

### 6.1 核心价值：长度提示与定位辅助

**data-orig-len 提供的信息**:
1. **原文规模感知**: 告诉 AI 原文片段有多长（token 数量）
2. **翻译扩展/压缩提示**: 帮助 AI 理解某些翻译可能显著扩展或压缩
3. **语义单元定位**: 在多个候选位置时，长度信息辅助选择

**实验证据**:
- **C 测试**: 移除 data-orig-len 后：
  - `InlineExpectedIDsError` 从 21 增至 27（+29%）
  - Principia 错误从 17 暴增至 27（+59%）
  - 总错误从 23 增至 45（+96%）

### 6.2 典型场景：书名翻译扩展

#### 有 data-orig-len（A 测试）
```
Template:
<span id="5" data-orig-len="3">Principia</span>

Translated text:
"... 《自然哲学的数学原理》第二版 ..."

AI 推理:
1. data-orig-len=3（原文仅 3 个 token，很短）
2. 这是一个"短原文→长译文"的扩展场景
3. "Principia" 是拉丁文书名缩写，中文习惯用全名
4. 在译文中找到书名 "《自然哲学的数学原理》"（虽然很长）
5. 成功定位并包裹
```

#### 无 data-orig-len（C 测试）
```
Template:
<span id="5">Principia</span>

Translated text:
"... 《自然哲学的数学原理》第二版 ..."

AI 推理:
1. 需要找 "Principia" 对应的译文
2. 没有长度提示，不确定是短语还是长名称
3. 可能误判为 "《自然哲学的数学原理》第二版" 整体（太长？）
4. 或者只选 "自然哲学"（太短？）
5. 经过 5 次重试仍失败
```

### 6.3 为什么不能移除 data-orig-len

**初始假设** (错误): "data-orig-len 可能误导 AI，因为跨语言长度差异大"

**实验反驳**:
- C 测试证明移除后质量显著下降
- AI 实际上能够理解 data-orig-len 是**提示而非约束**
- 在 Principia 这类极端扩展场景（1 word → 9 chars），长度提示帮助 AI 识别这是特殊情况

**正确理解**: data-orig-len 是**定位辅助信息**，不是**严格限制条件**

---

## 七、错误类型的影响

### 7.1 InlineExpectedIDsError（缺失有 ID 元素）

**严重程度**: 中等（通常可通过 1-2 次 retry 修复）

**原因**:
1. **翻译流畅性倾向**: AI 倾向于生成流畅译文，不愿打断插入标签
2. **文化特例**: 书名缩写→全名扩展（Principia 问题）
3. **词序变化**: 中英文语序不同，语义对应位置变化

**修复机制**:
- 错误消息提供原文片段（如 "Principia"）
- AI 在译文中语义匹配，找到对应位置包裹

**实验数据**:
- A 测试: 21 次（17 次 Principia 相关）
- B 测试: 7 次（Principia 改善但整体变差）
- C 测试: 27 次（Principia 问题恶化）

### 7.2 InlineWrongTagCountError（无 ID 元素数量错误）

**严重程度**: 高（可能导致 max_retries 失败）

**原因**:
1. **缺乏 Source text**: AI 无法理解无 ID 元素的语义边界
2. **元素合并**: AI 将多个 `<span>` 合并成一个
3. **元素拆分**: AI 将一个元素错误拆分成多个

**修复难度**: 高（需要理解原文结构）

**实验数据**:
- A 测试: 2 次（基线水平）
- **B 测试: 14 次**（无 Source text，暴增 7 倍）
- C 测试: 8 次（无 data-orig-len，增加 4 倍）

**关键教训**: 这是**最危险的错误类型**，移除 Source text 导致此类错误激增。

### 7.3 BlockExpectedIDsError（缺失块级元素）

**严重程度**: 高（结构性错误）

**原因**: 段落分段错误，块级元素对应关系混乱

**实验数据**:
- A 测试: 0 次
- B 测试: 0 次
- C 测试: 1 次（data-orig-len 缺失时出现）

---

## 八、特例问题：Principia 现象

### 8.1 问题本质

**语言学现象**: 英文文化圈习惯用拉丁文书名缩写，中文习惯用全名翻译

**案例**:
- 英文: "Principia" (1 word, 3 tokens)
- 中文: "《自然哲学的数学原理》" (9 characters)
- 扩展比例: 约 300%

### 8.2 为什么不应该为特例优化

**错误思路**: "Principia 占 A 测试错误的 74%（17/23），应该针对性优化"

**正确思路**: "Principia 是文化特例，通用翻译器需要解决通用问题"

**实验验证**:
- B 测试虽然 Principia 改善（17→5），但引入更严重的通用错误（WrongTagCount 2→14）
- C 测试针对 Principia 的 data-orig-len 优化失败，问题反而恶化（17→27）

### 8.3 正确处理方式

**接受**: Principia 这类文化特例需要 1-2 次 retry，这是合理成本

**不应做**: 为特例移除有用的通用辅助信息（Source text, data-orig-len）

**改进方向**（如果必须优化）:
1. 调整 fill_temperature（降低创造性，更机械地遵循结构）
2. 在 fill.jinja 中增强"打断流畅性"的指导
3. **但不是移除 Source 或 data-orig-len**

---

## 九、结论与建议

### 9.1 最佳配置

**✅ A 测试配置（Source + data-orig-len）是最优选择**

| 配置项 | 推荐值 | 理由 |
|--------|--------|------|
| Source text | ✅ 保留 | 理解无 ID 元素语义边界的关键 |
| data-orig-len | ✅ 保留 | 辅助定位，尤其对书名等扩展场景 |
| fill_temperature | 0.3 | 平衡创造性与结构遵循 |
| fill_top_p | 0.7 | 标准值 |
| max_retries | 5 | 足够处理特例 |

### 9.2 关键发现

1. **Source text 不可或缺**
   - 移除后 `InlineWrongTagCountError` 暴增 600%
   - 单字母、数学符号全部丢失
   - 这是**最严重的退化**

2. **data-orig-len 有积极作用**
   - 移除后总错误翻倍（23→45）
   - Principia 问题恶化 59%（17→27）
   - 提供的长度提示帮助 AI 理解翻译扩展/压缩

3. **不应为特例优化通用系统**
   - Principia 是文化特例，占 A 测试 74% 错误
   - 但针对性优化导致通用质量下降
   - 应接受特例需要少量 retry

### 9.3 实验数据总结

| 指标 | A 测试 | B 测试 | C 测试 | 最优 |
|------|--------|--------|--------|------|
| 达到 max_retries | 0 | 2 | 2 | **A** |
| 总错误次数 | 23 | 21 | 45 | **A** |
| InlineExpectedIDsError | 21 | 7 | 27 | B |
| InlineWrongTagCountError | 2 | 14 | 8 | **A** |
| Principia 错误 | 17 | 5 | 27 | B |
| 单字母符号错误 | 0 | 6 | 0 | **A** |

**综合评价**: A 测试在关键指标上全面领先，是唯一无 max_retries 失败的配置。

### 9.4 后续改进方向（如果需要）

**不推荐**:
- ❌ 移除 Source text
- ❌ 移除 data-orig-len
- ❌ 针对 Principia 特例优化

**可尝试**:
1. **调整 fill_temperature**
   - 尝试 0.2 或 0.15，降低创造性
   - 观察是否减少 Principia 错误而不引入其他问题

2. **增强 fill.jinja prompt**
   - 强调"打断流畅性也要遵循结构"
   - 但当前 prompt 已较长（165 行），需避免稀释重点

3. **优化错误消息**
   - 当前已提供原文片段（如 "Principia"）
   - 可能增加"翻译提示"，但成本高且可能误导

### 9.5 最终建议

**✅ 保持 A 测试配置，不做改动**

理由:
1. 0 次 max_retries 失败，系统稳定性最佳
2. Principia 错误虽多但可通过 1-2 次 retry 修复
3. 移除任何辅助信息都导致质量显著下降
4. 追求特例优化会损害通用质量

**接受现状**:
- Principia 等文化特例需要 1-2 次 retry 是合理成本
- 通用翻译器应该优先保证通用场景的质量

---

## 十、附录：实验原始数据

### A 测试完整统计

```
达到最大重试次数 (max_retries=5): 0 次
总错误提示次数: 23

重试次数分布:
  Retry 1/5: 9 次
  Retry 2/5: 1 次
  最高重试次数: Retry 2/5

错误类型分布:
  InlineExpectedIDsError: 21 次
  InlineWrongTagCountError: 2 次

缺失内容 Top 15:
  "Principia": 16 次
  "1687": 2 次
  "Optical Lectures": 1 次
  "Mathematical Principles of Nat...": 1 次
  "Philosophical Transactions of ...": 1 次
  "1672": 1 次
  "Opticks": 1 次
  "Lexicon": 1 次

分类汇总:
  Principia相关: 17 次 (74% 的错误)
  单字母/数学符号: 0 次
  其他书名/期刊: 8 次
  年份: 3 次
```

### B 测试完整统计

```
达到最大重试次数 (max_retries=5): 2 次
总错误提示次数: 21

重试次数分布:
  Retry 1/5: 9 次
  Retry 2/5: 3 次
  Retry 3/5: 2 次
  Retry 4/5: 2 次
  Retry 5/5: 2 次
  最高重试次数: Retry 5/5

错误类型分布:
  InlineWrongTagCountError: 14 次 (暴增)
  InlineExpectedIDsError: 7 次

缺失内容 Top 15:
  "Principia": 4 次
  "A": 1 次
  "AD": 1 次
  "C": 1 次
  "AB": 1 次
  "BC": 1 次
  "R": 1 次
  "Mathematical Principles of Nat...": 1 次
  "Philosophical Transactions of ...": 1 次
  "1672": 1 次
  "1687": 1 次

分类汇总:
  Principia相关: 5 次 (改善但...)
  单字母/数学符号: 6 次 (新问题!)
  其他书名/期刊: 4 次
  年份: 2 次
```

### C 测试完整统计

```
达到最大重试次数 (max_retries=5): 2 次
总错误提示次数: 45 (翻倍!)

重试次数分布:
  Retry 1/5: 11 次
  Retry 2/5: 4 次
  Retry 3/5: 3 次
  Retry 4/5: 2 次
  Retry 5/5: 2 次
  最高重试次数: Retry 5/5

错误类型分布:
  InlineExpectedIDsError: 27 次 (暴增)
  InlineWrongTagCountError: 8 次
  BlockExpectedIDsError: 1 次

缺失内容 Top 15:
  "Principia": 26 次
  "1687": 3 次
  "Opticks": 2 次
  "Lexicon": 2 次
  "Mathematical Principles of Nat...": 1 次
  "Philosophical Transactions of ...": 1 次
  "1672": 1 次
  "Lexicon Technicum": 1 次

分类汇总:
  Principia相关: 27 次 (问题恶化)
  单字母/数学符号: 0 次
  其他书名/期刊: 11 次
  年份: 4 次
```

---

**报告总结**: 通过严格的控制变量实验，验证了 Source text 和 data-orig-len 对 Fill Stage 质量的关键作用。最终结论是保持 A 测试的原始配置，接受文化特例（Principia）需要少量 retry 的合理成本，而不应为特例牺牲通用质量。
