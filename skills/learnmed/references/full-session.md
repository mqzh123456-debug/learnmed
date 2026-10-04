# 一个完整的跨天学习示例

以下材料、学生和作答均为自编示例，不是摘抄教材或真实学习记录。用于展示过程及复现工具行为，不证明学习效果。

## 输入

学生：“我是大二医学生，今天20分钟，考试还有两周。教材读得慢，帮我学这段并记下来，明天复习。”

S1：自编生理学示例A，第1节，无页码：

> 简化系统灌注模型中，平均动脉压与心输出量和总外周阻力有关；心输出量由心率和每搏量共同决定。压力感受器把动脉壁牵张的变化转成传入信号，经中枢整合调节自主神经输出。此反射主要参与短期血压调节。本模型未涵盖全部机制。

## 第一轮：有目标，只有一个小步骤

助手可回应：

“今天只学会两件事：解释这段的决定因素，并说清反射路径。没有学校大纲，下面是按本段主线选的学习重点。用3分钟看起点、8分钟理解、6分钟自测、3分钟收尾。今天记录在你的 learning-data 目录。

心率表示每分钟跳几次，每搏量表示每次泵出多少血，它们共同影响每分钟泵出的血量。先不展开其他调节机制。

现在遮住材料：心率不变、每次泵出的量增大时，每分钟泵出的血量会怎样？用一句话说明理由。你的信心是低、中还是高？”

此时停止等学生答，不展示答案或一整套题解。知识点初始状态未检测，即使已保存。

## 第二轮：纠错，不替学生虚构回答

学生：“不变，只由心率决定。高信心。”

助手：“你注意到了心率保持不变；缺口在于漏掉了每搏量。S1明确说两个量共同决定心输出量。用‘次数和每次的量’来判断，不能只看次数。现在试一题：如果每次的量不变而次数减少，每分钟总量会怎样？”

原始作答和错因被保留；即使学生随后纠正成功，也注明是否用过关键提示。最后学生用自己的话写主线，助手补成短记录。

当学生确认实际学习20分钟后，写入 session。未确认的耗时不填20分钟实际完成。记录示例：K1 wrong/high；K2（反射时间尺度）hinted/medium；下次建议次日。教材没出现的具体神经、药物和疾病不加进本次计分答案。

## 次日：读回后，先问旧错误

学生：“今天10分钟，接着昨天。”

助手读回到期队列，知道昨天是高信心漏掉每搏量；先给一道没有答案的变式题，而非重新生成整段摘要。学生独立答对，保存新session。此时只有一次独立成功日，状态 recalled，次日仍检测。随后另一天再次无提示答对才有 delayed 保持证据。

保存后输出可很短：“今天独立纠正了K1的决定因素错误。K2还需要回忆；K1建议明天再测。已保存：实际个人文件路径。下一次先解释两种决定因素，再继续未学段落。”

没有文件工具时明确未保存，并把S1、K1/K2、原始答错、提示、评分、停读位置和下次问题一起放进接续包。下次没有接续包就不能假装读到历史。

## 复现工具，不需要模型API

技能的 `assets/demo-material.json`、`demo-review-day1.json`、`demo-review-day2.json` 全是自编数据。两个检测文件分别模拟第一天独立回忆正确、第二天独立应用正确，以清楚展示不同日期证据；这与上文先犯错的对话是两个不同演示，不能混作同一个学生历史。

在仓库根目录运行，先选一个未使用的个人文件名：

```text
python skills/learnmed/scripts/learning_store.py --store learning-data/demo.learnmed.json init --on 2026-10-04
python skills/learnmed/scripts/learning_store.py --store learning-data/demo.learnmed.json upsert --input skills/learnmed/assets/demo-material.json --on 2026-10-04
python skills/learnmed/scripts/learning_store.py --store learning-data/demo.learnmed.json record --input skills/learnmed/assets/demo-review-day1.json --on 2026-10-04
python skills/learnmed/scripts/learning_store.py --store learning-data/demo.learnmed.json record --input skills/learnmed/assets/demo-review-day2.json --on 2026-10-05
python skills/learnmed/scripts/learning_store.py --store learning-data/demo.learnmed.json due --on 2026-10-08 --minutes 5
```

这是显式设置时间的模拟，不代表记录未来真实学习。预期：K1 在第二次提交后为 transfer-supported，建议复习日期2026-10-08；10月8日到期队列不包含答案。重复提交完全相同的session返回 already-recorded，次数不增加。init再次执行会拒绝覆盖。
