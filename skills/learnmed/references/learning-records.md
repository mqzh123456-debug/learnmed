# 可持续的学习记录

## 选择记录方式

默认在用户的私有工作目录创建 `learning-data/`，而非修改安装后的 skill 或把数据存进公开仓库。支持文件和 Python 时使用随技能携带的工具；只支持文档编辑时用下面的 Markdown 合同；只有聊天能力就输出同样信息的接续包。工具不是学习的前置条件。

学生请你记录学习，通常已授权在其工作目录写学习记录。复用其指定位置与格式。云文档/Anki连接/代码托管需要对应访问能力及授权，未实际执行时不要声称同步、导入或提醒已建立。目录可能被用户的云盘自动同步；“本地工具无网络”不意味着操作系统不会同步文件。

维护三个层次：

1. **课程和范围**：教材版本、课程目标（已知部分）、考试日期/体系、语言、当地时区、停读位置及未处理范围。用 `learning-data/profile.md`；未知字段写未知，不强制学生填写。
2. **知识点**：稳定ID、主题、简短标题、优先级与理由、提取问题和核验答案、来源、关系、别名、待确认事项。工具保存在一个 `personal.learnmed.json`。
3. **学习证据**：日期、实际时长或未知、原题、原始作答、提示、信心、评分与依据、错误类型、下次动作。工具的 sessions 追加保存；阅读但未答题可保存空 attempts。人类可读的日记可另外短写到 `learning-data/daily/YYYY-MM-DD.md`。

不要把每次聊天全文当知识库。保留影响复习和判断的证据即可。人工 Markdown 最小合同：

```markdown
日期/时区：
来源/已读范围/停读位置：
知识点ID/主线/与旧知识的关系：
题目/原始作答/提示/信心：
评分/正确要点/来源/错因：
未检测或待核验事项：
下次日期/无答案的复习任务：
保存状态/文件位置：
```

## JSON 工具的边界

`scripts/learning_store.py` 是 Python 3.10+ 标准库工具，无服务、网络或第三方依赖。日期显式使用学生本地 `YYYY-MM-DD`，默认时区 Asia/Shanghai，可在 init 指定其他 IANA 时区。Windows缺时区数据库时显式传 `--on`，无需为此安装包。

命令全局参数 `--store` 在子命令前：

```text
python <skill-dir>/scripts/learning_store.py --store learning-data/personal.learnmed.json init --on 2026-10-04
python <skill-dir>/scripts/learning_store.py --store learning-data/personal.learnmed.json upsert --input learning-data/material.json --on 2026-10-04
python <skill-dir>/scripts/learning_store.py --store learning-data/personal.learnmed.json record --input learning-data/review.json --on 2026-10-04
python <skill-dir>/scripts/learning_store.py --store learning-data/personal.learnmed.json due --on 2026-10-05 --minutes 8
python <skill-dir>/scripts/learning_store.py --store learning-data/personal.learnmed.json summary --on 2026-10-10
python <skill-dir>/scripts/learning_store.py --store learning-data/personal.learnmed.json export-anki
```

命令中的日期仅是语法示例。实际使用代入当前日期；历史日期不得伪装成今天。`--on` 指定本次操作的本地日期，`record` 拒绝把更晚日期记录为已完成。只读 `due/summary` 可查看未来计划。检查退出码和返回的 `written`，再读回 affected IDs 或到期队列。脚本不支持自定义间隔、考试日期、手动覆盖状态或撤销记录；复杂安排放到个人计划中，不能冒充脚本支持这些功能。

## 输入合同

`upsert` 输入顶层只接受 `sources`、`concepts` 列表；只更新资料，不提高掌握状态。

```json
{
  "sources": [
    {"id": "S1", "title": "自编生理学示例A", "locator": "第1节（无页码）", "verification": "verified"}
  ],
  "concepts": [
    {
      "id": "K1", "title": "心输出量的决定因素", "topic": "生理学/循环",
      "priority": "core", "priority_reason": "本节主干关系",
      "source_ids": ["S1"], "verification": "verified",
      "prompt": "心输出量由哪两个量共同决定？",
      "answer": "心率和每搏量。",
      "estimated_minutes": 2, "aliases": ["每分钟泵血量的决定因素"],
      "related_ids": [], "tags": ["机制"]
    }
  ]
}
```

`verified` 表示助手实际依据可读取来源核对过本条内容，**不表示教材或助手不会出错**。原始出处缺失、OCR歧义或临床信息未核验用 `pending`，知识点同样标 pending。不能给无来源知识点填伪造 S1 来绕过核验。

`record` 输入保存真实学习证据：

```json
{
  "id": "2026-10-04-circulation-01", "date": "2026-10-04", "minutes": 5,
  "attempts": [
    {
      "concept_id": "K1", "prompt": "心输出量由哪两个量共同决定？",
      "user_answer": "只有心率", "expected_answer": "心率和每搏量。",
      "source_ids": ["S1"], "result": "wrong", "confidence": "high", "kind": "recall",
      "error_type": "遗漏决定因素", "feedback": "漏掉每次泵出的量。", "hint": "none"
    }
  ],
  "notes": "本人确认实际学习5分钟。待回忆验证，每搏量尚需复习。"
}
```

字段约束：ID 用字母/数字/点/下划线/连字符；`priority` 为 core/important/extension；`result` 为 wrong/partial/hinted/correct；`confidence` 为 low/medium/high/unknown；`kind` 为 recall/application。所有医学答案有 source_ids；`user_answer` 不能为空，没有答题用空 attempts。学生明确回答“不会”算一次失败尝试，保留原文。一次session可包含多个知识点的作答。工具不自动判医学正误，评分前由助手核对；提示、错因、评分依据可追加在 attempt。

同一ID相同内容重试不重复计数，内容不同则拒绝覆盖。资料更正用同一知识点ID upsert：prompt、answer、source_ids、核验状态或来源内容变化会增加版本并重新安排检测；原作答留在旧版本。工具在 concept_history 和 source_history 保存旧内容，在每次检测的 source_snapshot 保存当时出处，包括未检测过的旧答案也能保留。revision_date 记录当前版本生效日期，之前的测验不得计入新版。仅标题、标签或预计时间变化不会抹去证据。保留关键修改原因在 notes 或日记中。

同主题同名不同ID会拒绝；语义相同的不同标题由助手判断并复用原ID。`aliases` 可存原来新笔记的别名，但不能占用另一个现有知识点ID。若旧库已存在两个独立ID，不假装脚本完成历史合并：先提出人工迁移方案保留两边历史，或标记待归并；当前脚本不提供删除/merge。

sessions 按日期顺序追加。工具不支持倒序补记旧测验，以避免扰乱复习状态；旧纸质资料可写人工历史日记，当前重新检测再入库。`summary` 的7日作答/时长统计是窗口统计，`current_status_counts` 是当前知识库状态，不能混成历史日期当时的快照。

## 状态与保存机制

脚本根据当前版本的已记录作答计算状态：untested / relearn / developing / supported / recalled / retained / transfer-supported；待核验为 pending。每个错误/部分/提示正确中断当前独立成功序列。不同日期连续成功才增加间隔；含一次应用且至少两个日期成功为 transfer-supported。当前状态不能替代细读错因与原始证据。

写入先验证整批内容，再在同目录完成临时文件后原子替换。Windows短暂文件占用最多尝试4次（总等待约0.3秒），仍失败则保留原记录并报告错误。`.lock` 避免并发修改；有锁时停止，先确定是否仍有写入进程，不能自动删掉另一个运行任务的锁。读文件失败、版本不支持或资料冲突时不重建覆盖。新建 `init` 永不清空现有文件。仍应由用户自行备份重要记录；原子替换不能防止人为删除或设备故障。

## Anki 导出

导出只包含已核验内容，UTF-8、三个字段 Front / Back / Tags，来源放在 Back。Front带稳定ID便于识别；HTML控制字符先转义，换行变成 `<br>`。只导出学习内容，不包含原始作答；待核验内容不进入正式卡。

PowerShell保存示例：

```powershell
python skills/learnmed/scripts/learning_store.py --store learning-data/personal.learnmed.json export-anki | Set-Content -Encoding utf8 learning-data/anki.tsv
```

在 Anki 手动导入文本文件，选择可用的基础正反面笔记类型，将1、2、3列映射到 Front、Back、Tags，开启HTML，并先预览小样。系统语言可能改变笔记类型/字段名称，因此不硬编码notetype。这里生成的是TSV，不是 `.apkg`，也没有执行导入、AnkiConnect或同步。Anki使用自己的调度；不将该工具到期日期强行导入覆盖既有记忆历史。重复导入前核对 Anki 的重复处理设置。[Anki 官方文本导入说明](https://docs.ankiweb.net/importing/text-files.html)
