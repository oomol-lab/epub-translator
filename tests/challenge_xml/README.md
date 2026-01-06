# Missing Span ID Challenge

## 问题描述

这是一个典型的"翻译改变语序导致 LLM 无法定位 span ID"的案例。

### 原始片段（关键部分）

```
The reviewer of the first <span id="5">Principia</span> in the <span id="6">Journal des Sçavans</span> could...
```

### 翻译后

```
《学者杂志》上对<span id="5">《原理》</span>的评论者可以...
```

### 问题

1. **语序变化**：英文"X in Y" → 中文"Y上对X"
2. **显著性丢失**："Journal des Sçavans"（明显的期刊名）→ "学者杂志"（普通词汇）
3. **LLM 困境**：收到"Missing <span id=\"6\">"错误，但不知道：
   - id="6" 原文是 "Journal des Sçavans"
   - 译文中的"学者杂志"就是对应词
   - 需要将"学者杂志"用 `<span id="6">` 包起来

## 重试历史

该案例在 4 次重试中的表现：

1. **尝试 1-2**：缺少 `<span id="5">` 和 `<span id="6">` 
2. **尝试 3-4**：只缺 `<span id="6">` （成功添加了 id="5"，但 id="6" 仍未找到）

## 日志文件

重试序列：
- `temp/logs/request 2026-01-06 10-04-57 222331.log` (尝试 1)
- `temp/logs/request 2026-01-06 10-05-06 745276.log` (尝试 2)
- `temp/logs/request 2026-01-06 10-05-27 998552.log` (尝试 3)  
- `temp/logs/request 2026-01-06 10-05-36 895056.log` (尝试 4)

## 测试文件

- `missing_span_id_challenge.xml` - XML 模板（包含结构和 ID）
- `missing_span_id_challenge.source.txt` - 原文
- `missing_span_id_challenge.translation.txt` - 译文

## 预期解决方案

需要在 fill.jinja 中添加"文本-结构映射"指导，帮助 LLM：
1. 识别原文中的命名实体（Book A, Journal B）
2. 找到译文中的对应翻译（书A, 期刊B）
3. 根据模板 ID 映射，不受语序变化影响
