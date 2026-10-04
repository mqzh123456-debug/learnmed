# LearnMed

一个面向医学生自主学习的 Agent Skill。帮助你把教材与讲义变成可理解、可自测、可复习、可持续积累的知识。

它会带你完成“小段导读 → 尝试回忆 → 按错因解释 → 变式检测 → 精简归纳 → 保存记录 → 跨天复习”。你也可以只要求某一步；读过和真正独立答对会分别记录。

## 直接开始

技能入口：[skills/learnmed/SKILL.md](skills/learnmed/SKILL.md)。在能读取仓库的助手中说：

> 请读取 skills/learnmed/SKILL.md，按 LearnMed 带我学习。今天25分钟，这是教材片段……请先带我理解一小段，等我作答后再给答案，最后记录到 learning-data。

安装到支持 Agent Skills 的环境后，可直接调用：

> $learnmed 我是大二医学生，今天20分钟。帮我读这段生理学教材，说明学习重点，检测我的理解，记录下来明天继续。

> $learnmed 读取我的 learning-data，今天只有10分钟，优先复习上次错的内容。

> $learnmed 我总混淆这两个概念。先让我解释，再根据错误帮我整理对照。

> $learnmed 复盘本周学习，找出反复错误、未检测部分和下周最值得调整的一件事。

提供相关教材片段、截图或可读文件即可。课程大纲、教师要求和考试范围有助于判断重点；没提供时，助手给出明确标注的学习优先级建议。

## 安装与运行环境

将整个 `skills/learnmed` 文件夹（包含 references、assets、scripts、agents）复制到当前工具支持的技能目录。在 Codex 中，可使用 skill-installer 从此仓库的 `skills/learnmed` 路径安装；也可按 [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills) 设置本机或项目技能目录。只安装SKILL.md会丢失记录工具与按需参考文件。

普通聊天环境可以手动提供技能入口及所需参考文件，并以接续包保存进度。是否自动识别、是否能写文件由使用环境决定；下载仓库本身不会自动启用技能。

可选的本地记录工具需要 Python 3.10+，**无需 API key、第三方包、Anki 或云服务**。助手负责医学内容核对和评分，工具负责可靠保存、状态计算、到期选择与TSV导出。不能写文件时仍可学习，但需自己保存助手给出的接续包。

## 每天能积累什么

| 你的困难 | LearnMed 提供的帮助 |
|---|---|
| 教材很长，读完没有主线 | 按时间缩小范围、按依据选核心、用问题导读 |
| 看懂但说不出来 | 自己先解释或回忆，再补前提与机制 |
| 只会原题、容易混淆 | 变式、自解释、同维度比较与适度应用 |
| 学完没有合适的检测 | 少量可核验题目，先作答后反馈 |
| 笔记越来越多，却难以复习 | 复用知识点ID、合并同义标题、保留关系和来源 |
| 第二天忘了昨天学什么 | 读回原始作答、错误和到期任务，先测再看 |
| 复习积压、时间不够 | 按预算选少量项目，减少新卡，不重置全部日期 |

## 完整示例与文件结构

[跨天学习示例](skills/learnmed/references/full-session.md) 包含互动过程和能直接运行的自编数据演示。

```text
skills/learnmed/
  SKILL.md                 学习流程和按需路由
  agents/openai.yaml       技能界面信息
  references/              导读、自测、记录、研究依据、完整示例
  scripts/learning_store.py 本地记录工具
  assets/demo-*.json       自编示例输入
tests/                     工具行为测试
docs/                      验证计划、场景和实际评估结果
```

记录说明：[learning-records.md](skills/learnmed/references/learning-records.md)。方法和来源：[evidence.md](skills/learnmed/references/evidence.md)。

## 学习资料留在你自己的工作目录

个人记录默认放在 `learning-data/`；仓库 `.gitignore` 已忽略该目录和 `*.learnmed.json`。这不是自动访问控制：在其他目录保存或强制提交仍可能暴露资料。不要将完整教材、成绩、患者信息或私人作答推送到公开仓库。

记录文件包含稳定知识点、来源、原始作答和复习日期；没有后台自动提醒，也不自动上传或同步。Anki导出是带来源的UTF-8 TSV，需要你手动导入，保留Anki自己的调度。

## 验证与实际边界

在仓库根目录运行：

```text
python -m unittest discover -s tests -v
```

[评估结果](docs/evaluation-report.md) 说明独立模拟、软件测试、发现的问题和修正。主动回忆与分散练习有研究支持；技能中的题量、时间分配、掌握状态门槛和复习间隔是可调整的工程默认值。尚未做真实学生长期效果试验，不能保证考试成绩或临床胜任能力。临床知识变化或教材识别错误仍需核验。
