# 基于 StatsBomb 开放数据的足球战术分析与可视化系统设计与实现

---

**学校：** 上海第二工业大学
**学院：** 计算机与信息工程学院
**专业：** 计算机科学与技术
**姓名：** 徐张睿遥
**学号：**
**指导教师：**
**日期：** 2026 年 10 月

---

## 摘要

足球比赛的公开事件数据记录了每一次传球、射门、对抗和防守动作，这类数据为战术分析提供了可量化的依据。本课题以 StatsBomb 开放数据为数据来源，设计并实现了一套面向单场比赛的足球战术分析与可视化系统 FTAS。系统先用 pandas 把原始 JSON 事件数据整理成数据框，按统一口径计算传球、射门、控球和压迫等统计指标，再用 mplsoccer 绘制传球网络图、射门分布图和活动热力图，最后把统计结果压缩成一份结构固定的摘要 JSON。摘要 JSON 交给大语言模型生成中文战术解读，提示词限制模型只引用摘要中的数字，输出再由程序校验段落结构与数字一致性，不合格就纠错重试一次，模型不可用时回退到本地缓存结果。服务端用 FastAPI 提供查询比赛、生成分析和返回图片的接口，前端是原生 HTML、CSS、JavaScript 页面，支持球队名模糊匹配与输入补全。系统以 Docker 部署，并提供一个不依赖网络的离线静态演示包。在一场西甲联赛的样例中，系统给出巴塞罗那传球 973 次、传球成功率 91.0%、射门 9 次、射正 6 次等指标，并生成三张战术图与一段中文解读。系统可以作为高校体育数据教学和战术解读的轻量工具。

**关键词：** 足球战术分析；StatsBomb 开放数据；数据可视化；传球网络；大语言模型

## Abstract

Public event data of football matches records every pass, shot, duel and defensive action, which gives tactical analysis a quantitative basis. This project designs and implements FTAS, a football tactical analysis and visualization system for single matches, using StatsBomb open data as its only data source. The system first converts raw JSON event data into data frames with pandas, computes statistics on passing, shooting, possession and pressing under unified definitions, then draws a pass network, a shot map and an activity heatmap with mplsoccer, and finally compresses the statistics into a summary JSON with a fixed structure. The summary JSON is sent to a large language model to produce a Chinese tactical commentary. The prompt restricts the model to numbers in the summary, and the output is checked by code for section structure and numeric consistency; a failed check triggers one corrective retry, and an unavailable model falls back to the cached result. The server exposes interfaces for match query, analysis and figure retrieval through FastAPI, and the front end is a plain HTML, CSS and JavaScript page that supports fuzzy team matching and input suggestions. The system is deployed with Docker and ships an offline static demo package that needs no network. On a sample La Liga match, the system reports 973 passes, a 91.0% pass accuracy, 9 shots and 6 shots on target for Barcelona, together with three tactical figures and a Chinese commentary. The system can serve as a lightweight tool for sports data teaching and tactical interpretation in universities.

**Key words:** football tactical analysis; StatsBomb open data; data visualization; pass network; large language model

## 目录

- 摘要
- Abstract
- 第一章 文献综述
- 第二章 绪论
- 第三章 相关技术与数据基础
- 第四章 系统需求分析
- 第五章 系统设计
- 第六章 系统实现
- 第七章 系统测试与运行结果
- 第八章 总结与展望
- 参考文献
- 附录 A 主要文件清单
- 附录 B 环境与运行说明


## 第一章 文献综述

本章梳理作者提供的两篇文献，并说明它们与本课题的关系。两篇文献一篇讨论体育数据分析的基础设施，一篇讨论足球战术的自动生成，分别处在这条链路的两端。

### 1.1 容器化的大数据体育分析架构

第一篇文献是《A Dockerized Big Data Architecture for Sports Analytics》，作者是土耳其科贾埃利大学的 Yavuz Melih Özgüven、Utku Gönener 和 Süleyman Eken，发表在《Computer Science and Information Systems》2022 年第 19 卷第 2 期，第 957 至 978 页。

文章从体育数据规模的增长写起。比赛和训练中的可穿戴设备、传感器与定位技术产生大量数据，如果把来自多个来源的体育数据交给集中式系统汇总和分析，数据的准确性和时效性都会受影响，因此作者主张把分布式和并行计算引入体育数据分析。文中同时指出一个具体缺口：当时基于 MapReduce 的计算框架对"复用已有处理工具"的支持不足。

文章给出两项贡献。第一项是一个开源架构，在 Apache Spark 之上加入对 Docker 容器的支持；第二项是在四个数据密集型案例上验证这套架构，分别对应结构化分析、流式处理、机器学习方法和图分析。作者列出容器化带来的几项好处：跨平台和跨云的可移植性；相比虚拟机占用更少资源、计算利用率更高；便于接入既有的 DevOps 流程；通过隔离应用改善安全性；启动更快、更容易扩展。

四个案例的具体做法如下。

结构化分析用类 SQL 的方式处理球员数据，处理过程被封装成容器镜像、输入与输出挂载点，再由框架调度执行。

流式处理把 Spark Streaming 与 Apache Pulsar 结合，用于多模态体育数据的异常检测；文中也提到在足球场场景下做实时事件检测的工作。

机器学习部分用 FIFA 20 的完整球员数据做回归和聚类，回归比较了线性回归、决策树回归和随机森林回归，用 R² 与 RMSE 评价；聚类按守门员特征分组，用轮廓系数选择簇数，比较了 Bisecting K-means、高斯混合和 K-means。分类任务使用 2000 至 2017 年的 ATP 比赛数据，预测球员能否赢得比赛，比较了逻辑回归、决策树和随机森林三种方法，三者精确率在 0.62 至 0.66 之间，召回率在 0.84 至 0.91 之间，F1 值在 0.69 至 0.73 之间。

图分析部分与本课题最接近。作者用 StatsBomb 的事件数据构建足球传球网络：节点是同一支球队的球员，边表示两人之间的传球关系；可视化时，节点位置取球员传出或接球时的平均位置，节点大小随传球次数变化，边的颜色按两名球员之间的传球次数分档（0 至 9、10 至 19、20 至 29、30 以上），球员姓名标注在节点附近。文中给出的一张示例图是巴塞罗那对阵拉科鲁尼亚时的传球网络。

除技术方案外，文章还讨论了数据集查找和代码仓库分析。作者把体育数据分为原始数据、抽取事件和统计指标三类，来源包括官方网站、公开 API、整理好的数据库以及 GitHub 上的工具；他们用 git 命令行工具统计了 GitHub 上以 "sport analytics" 为主题的仓库，共 297 个，主要语言是 Jupyter Notebook（67 个）、Python（45 个）和 R（44 个）。作者把可复现性作为评价标准，认为研究者应当公开数据和代码。

### 1.2 足球开放进攻中的战术生成

第二篇文献是 TacEleven，作者是 Siyao Zhao、Hao Ma、Zhiqiang Pu、Jingjing Huang、Yi Pan、Shijie Wang 和 Zhi Ming，作者单位包括中国科学院自动化研究所复杂系统认知与决策智能重点实验室、中国科学院大学、上海人工智能实验室和 AJ Auxerre 俱乐部。这是一份预印本，未标注出版信息。

文章关注开放进攻中的战术发现问题。足球比赛的进攻优势大多在开放进攻中形成，而开放进攻高度动态、序列很长，随着进攻推进，可能的战术空间呈指数增长，人工逐条枚举不现实。作者指出，已有的自动化方法大多针对静态场景（例如角球一类的定位球），开放进攻基本没有被覆盖，教练和分析师只能在已知战术上做小幅调整。

TacEleven 的做法是把一个战术拆成若干"事件级文本—轨迹对"：每一对包含一句事件描述（例如"传球给内马尔（左前腰）"）和一条与之对应的具体轨迹，说明这个动作如何完成。一个开放进攻战术就是由一对或多对按顺序组成的连贯序列，生成时既依赖历史上下文，也要对齐一句高层战术指令。

框架由两个部件组成。生成器是在作者构建的数据集上训练的时空图生成模型，数据集包含超过一百万条文本—轨迹对，由事件数据与追踪数据对齐得到；生成器学习文本描述与具体轨迹之间的对应关系，因此在同一段历史情境下，改变描述文字就能得到不同的轨迹，用于反事实探索。评论器基于多模态大语言模型，对候选战术的质量和可行性做推理评估，选出与战术指令最匹配的一个，并给出选择的理由。两个部件构成闭环：被选中的轨迹作为下一步的历史上下文，生成器继续给出候选，评论器继续评估，从而以自回归方式生成多步战术，作者把这一过程称为反事实战术树搜索。

评估分成三个复杂度递增的任务：反事实探索、单步发现和多步发现。评价指标包括反事实结果与语言描述的一致性 C、进球概率的变化 ΔxG、威胁值的变化 ΔxT，以及控球权价值的变化 ΔPC，后三项分别对进攻方和防守方计算。单步发现任务中，全队范围内的一致性为 92.0%，ΔxG 提升 0.016；按位置细分，后场一致性 93.3%，中场 93.3%，前场 87.5%。作为对照，从候选中随机选择的一致性为 84.0%，而真实发生的情况为 96.0%。多步任务按"激进""保守""中性"三种指令风格生成战术，其中激进风格的一致性为 89.2%，ΔxG 提升 0.017。

文章还做了规模实验：训练数据从 10.8 万条增加到 107.6 万条，模型参数从 500 万增加到 13.73 亿，反事实对齐误差和真实轨迹误差都随之下降，最终分别收敛到 5 米和 2 米左右。

定量指标之外，作者与 AJ Auxerre 的教练和分析师合作发放问卷，共 36 人参与。第一份问卷把真实战术与生成战术混在一起且不标明来源，让参与者判断两者是否可区分，三组参与者的判定均值都接近 0（球员 0.00，从业者 0.08，专家 −0.05），说明即便是专家也很难区分生成的战术与真实战术。第二份问卷明确标注来源，让参与者比较生成战术与真实战术，平均 44.46% 的生成战术被认为更好（27% 更差，28% 没有变化），专家组的这一比例是 34.00%。多步战术中有 52.50% 被认为可以在真实的高水平比赛中采用。

文章在讨论部分把自身与已有工作做了对比：以往研究多集中在静态场景（如 TacticAI）或时间跨度较短、条件灵活性有限的动态任务上，TacEleven 用事件序列解耦的方式支持长序列生成，并以自然语言作为条件，让使用者参与战术探索。

### 1.3 两篇文献的评述与本课题的定位

两篇文献处理的是同一条分析链路上的不同问题。文献[1]回答"用什么基础设施跑分析"：面对多来源、大体量的体育数据，作者用 Apache Spark 加 Docker 容器搭出可以复用的处理平台，并用四个案例证明这套平台能承载结构化分析、流式处理、机器学习和图分析四类负载。文献[2]回答"能从数据里得到什么战术"：它不满足于描述已发生的比赛，而是用生成模型和语言模型给出新的战术方案，再请专家判断方案是否可用。

从本课题的角度看，两篇文献各有可以借鉴的部分，也各有超出本课题范围的部分。

可以借鉴的第一点是数据来源与表示方式。文献[1]的图分析案例同样使用 StatsBomb 事件数据构建传球网络，节点位置取球员的平均位置、节点大小随传球次数变化、边的颜色按传球次数分档，这套表示与本系统的传球网络图一致，说明它是这类数据下比较通行的画法。本系统在此基础上补上了球员姓名标注、节点与连线的连续缩放，并把网络统计量（传球边数、球员网络连接度）接入文字指标的计算。

可以借鉴的第二点是让语言模型参与战术解释。文献[2]用多模态大模型充当评论器，对候选战术做推理、筛选并给出理由；本系统让大模型根据统计摘要写战术解读，思路相同。区别在于角色不同：文献[2]让模型在若干候选方案之间做选择，属于生成与决策；本系统让模型把已经算好的统计数字组织成文字，不参与战术的生成和排序。

可以借鉴的第三点是容器化交付。文献[1]列举的可移植性、资源占用和启动速度等好处同样适用于本系统。本系统用单个 Docker 镜像交付，把中文字体和运行依赖打进镜像、以非 root 用户运行，并额外准备了一套不依赖服务器和网络的离线静态包，用于会场网络不可用的场合。

超出本课题范围的部分也很明确。文献[1]面向需要集群承载的大规模多源数据，而本系统只处理单场比赛的事件数据，一场比赛的 events.json 约 3.5 MB，本课题缓存的六场比赛事件数在 3497 至 4160 条之间，用 pandas 在单机上处理即可，引入 Spark 只会增加部署复杂度。文献[2]使用追踪数据训练生成模型，需要把事件数据与逐帧位置数据对齐，本系统只有事件数据，既没有追踪数据，也不生成新的战术，输出的是对已发生比赛的描述性统计和解读。

据此可以确定本课题的定位：在单场比赛、只有事件数据、单机部署这三个约束下，把从数据获取到图表、指标、文字解读和交付的链路做完整、做到可复现，并把统计口径与模型输出的边界写清楚。文献[1]说明了容器化和图分析用在体育数据上的可行性，文献[2]说明了语言模型在战术层面能达到的表达能力，本课题选择的是两者之间一个规模更小、但每个环节都能落地并且可以核对的位置。

## 第二章 绪论

### 2.1 研究背景

足球比赛的数据化程度在过去二十年里明显提高。商业数据公司对职业赛事逐场采集事件数据，记录每一次传球、射门、抢断、对抗的位置、时间与结果。这类数据把"球队怎么踢"从解说词变成了可以统计的对象。

与此同时，公开可用的数据仍然有限。职业俱乐部采购的商业数据价格高、授权严，高校教学和课程实践很难直接使用。StatsBomb 开放数据在这样的背景下成为一个可行的替代：它免费提供一批历史赛事的事件数据，覆盖世界杯、欧洲杯、美洲杯等国际大赛和西甲、英超、德甲、欧冠等联赛，许可为 CC BY-NC-SA 4.0，允许非商业用途的二次开发。数据本身有统一的坐标系统和字段命名，适合作为数据处理与可视化课程的素材。

拿到数据并不等于能做出分析。原始 JSON 的字段嵌套深，同一场比赛的事件数量在数千条量级，直接阅读没有意义；要把它们变成可判断的结论，需要经过字段解析、指标口径统一、图形表达和文字归纳几个环节。此外，指标口径本身是有歧义的：什么算"长传"、禁区用哪个范围、射正包含哪几种结果，不同做法会得出不同的数字。本课题要解决的，就是把这条链路完整地搭起来，并且把每一处口径写在代码里。

### 2.2 研究意义

从技术角度看，本课题把数据处理、统计计算、图形可视化、大语言模型接入和 Web 服务放到一个项目里跑通，覆盖了计算机专业本科阶段的主要工程环节。相比只做单个算法或单个图表的练习，它更接近一个完整的小型系统。

从教学使用角度看，系统把"输入球队名、选比赛、出图和分析"压缩成几次点击，不需要使用者写代码或了解 StatsBomb 的字段结构，因此可以用于体育数据分析的入门教学，也可以用于球迷视角的战术解读。

从方法角度看，本课题的一个重点是控制大语言模型的编造行为。足球领域有很多统计指标，模型很容易"顺手"给出摘要里并不存在的数字。系统通过提示词约束和输出校验两道关卡，把模型能说的话限制在已计算的统计范围内，这一点对其他"统计数据 + 大模型解读"的场景也有参考价值。

### 2.3 研究内容与目标

本课题的研究内容分为五部分。

一是数据获取与管理。通过 HTTP 直接请求 StatsBomb 开放数据仓库，按 match_id 建立本地缓存，使同一场比赛只下载一次。

二是数据处理与统计口径。把事件 JSON 展开成数据框，提取传球、射门、对抗等事件，按统一口径计算团队指标、战术风格指标、进攻偏好指标和球员指标。

三是可视化。绘制传球网络图、射门分布图和活动热力图三种图形，分别对应球队的传球结构、射门位置分布和触球活动区域。

四是自动解读。把统计结果组织成摘要 JSON 交给大语言模型，生成中文战术分析，并校验输出，防止模型引用摘要之外的数据。

五是系统集成与部署。用 FastAPI 提供服务接口，用静态页面提供交互界面，用 Docker 交付运行环境，并准备一套不依赖网络的离线演示方案。

本课题的目标是得到一个可以在普通电脑上运行、能够对任意一场已收录比赛生成完整分析结果的系统原型。

### 2.4 论文组织结构

本文共分八章。第一章是文献综述。第二章说明研究背景、意义、内容和论文结构。第三章介绍所用数据、坐标系统和主要技术组件。第四章分析系统的功能需求和非功能需求。第五章给出系统的总体架构、模块划分、数据流、统计摘要结构和接口设计。第六章按模块说明实现方法，并引用关键代码。第七章给出测试方法和运行结果。第八章总结工作并说明不足。

## 第三章 相关技术与数据基础

### 3.1 StatsBomb 开放数据

StatsBomb 是一家足球数据分析公司，它在 GitHub 上维护开放数据仓库 statsbomb/open-data，按赛事和赛季组织比赛数据。与本课题相关的文件有四类：competitions.json 记录赛事与赛季编号；matches/{competition_id}/{season_id}.json 记录该赛季全部比赛的元信息，包括对阵双方、比分、比赛日期；events/{match_id}.json 记录该场比赛的全部事件，是本课题的主要输入；lineups/{match_id}.json 记录双方阵容。单场比赛的 events.json 约 3.5 MB，事件数在数千条量级。

StatsBomb 使用固定坐标系统描述位置。球场按 120 码长、80 码宽建模，原点 (0, 0) 在球场左下角，x 轴沿球场长度方向指向进攻方向，y 轴指向球场宽度方向，球门中心位于 (120, 40)。本课题中的射门距离、禁区判断、左右路划分都基于这套坐标。

事件数据以"一次动作一条记录"的形式给出，每条记录包含若干公共字段和与该动作类型对应的专属字段（在 JSON 中以动作类型名作为前缀）。本课题用到的主要字段见表 3-1。

表 3-1 本课题使用的主要事件字段

| 字段 | 含义 |
| --- | --- |
| type.name | 事件类型，如 Pass、Shot、Carry、Pressure、Duel |
| location | 事件发生位置 [x, y] |
| player.name / team.name | 触球球员与所属球队 |
| minute | 比赛分钟 |
| possession / possession_team.name | 控球段编号与控球方 |
| pass.end_location / pass.length | 传球终点与传球距离（码） |
| pass.recipient.name | 接球球员 |
| pass.outcome.name | 传球结果，成功时该字段为空 |
| pass.cross / pass.through_ball | 是否为传中、是否直塞 |
| pass.shot_assist / pass.goal_assist | 是否为形成射门、形成进球的传球 |
| shot.outcome.name | 射门结果，如 Goal、Saved、Blocked、Post |
| carry.end_location | 带球终点 |
| duel.outcome.name | 对抗结果 |
| tactics.formation | 阵型编号，如 433 |

开放数据的许可为 CC BY-NC-SA 4.0，仅限非商业用途，使用时必须注明来源。本课题在每个页面的页脚标注了数据来源和许可，系统本身也只用于学习与技术演示。

### 3.2 pandas

pandas 是本课题的数据处理基础。事件 JSON 是嵌套结构，序列化成表格需要先展开。pandas 的 json_normalize 能把带嵌套字典的列表展开成扁平的 DataFrame，嵌套键用点号连接成列名，例如 type.name、pass.end_location。展开之后，筛选、分组、聚合都可以用 DataFrame 的表达完成，例如按 player.name 分组统计传球次数，或者按 team.name 过滤出某一方的事件。

选择 pandas 的原因不是它算法复杂，而是坐标系数据本身就是表格形式，用表格工具处理比手写循环更短、更不容易出错。

### 3.3 matplotlib 与 mplsoccer

matplotlib 是 Python 的绘图库，负责画布、坐标轴和图片输出。mplsoccer 是建立在 matplotlib 之上的足球绘图库，提供 Pitch 类。Pitch 对象在初始化时指定 pitch_type，就可以按对应数据提供方的坐标系统绘制球场线，并在同一套坐标系下叠加散点、折线、热力等图层。本课题使用 statsbomb 坐标类型，因此事件坐标与球场线无需换算即可对齐。

可视化部分还用到 matplotlib 的无界面后端 Agg。服务器和容器环境没有图形界面，调用默认后端会报错或阻塞，因此程序在导入 pyplot 之前把后端设为 Agg，保证图表可以在无 GUI 的环境下生成并保存为 PNG。

### 3.4 FastAPI、Pydantic 与 slowapi

FastAPI 是基于 Python 类型标注的 Web 框架，用装饰器声明路由，用类型标注声明参数，框架据此完成参数解析和校验，并自动生成接口文档。本课题的服务端由它提供。

Pydantic 负责请求体的结构校验。分析接口的请求体只需要 match_id、team_name 和 prompt 三个字段，其中 match_id 必须是正整数，其余两个字段不能为空，这些约束都写在请求模型里，避免非法请求进入后续流程。

slowapi 为接口提供按客户端 IP 的限流能力。分析接口会触发数据下载和模型调用，属于开销较大的操作，因此在设计上只对该接口限流。

### 3.5 大语言模型与 OpenAI 兼容接口

战术解读部分调用大语言模型。本课题使用 OpenAI 兼容的对话补全接口，默认服务商为 DeepSeek，默认模型为 deepseek-chat，通过 OPENAI_BASE_URL 和 LLM_MODEL 两个环境变量即可切换到其他兼容服务。模型输入由 system 与 user 两条消息组成：system 消息写死分析约束，user 消息携带统计摘要 JSON 和用户的自然语言请求。system 与 user 分离的作用是让用户输入无法覆盖 system 中的约束。

### 3.6 Docker

Docker 把运行环境和程序打包在一起。本课题的镜像基于 python:3.11-slim，安装中文字体（图表中文显示需要）和 OpenMP 运行库，创建非 root 用户运行服务，并把应用端口固定为 8000。部署时用 docker-compose 编排，把缓存目录挂载为数据卷，把密钥和模型参数通过环境变量注入，避免密钥写进镜像。

## 第四章 系统需求分析

### 4.1 使用角色与场景

系统的使用者是希望快速了解某场比赛战术特征的教师、学生或球迷。用户不需要了解 StatsBomb 的字段结构，也不需要会写代码，只需要知道球队名，并大致知道比赛属于哪项赛事。

典型场景是：用户打开页面，输入球队名，从列表里选择一场比赛，写一句分析要求，点击分析，等待十几秒到几十秒，得到三张图、一张统计对比表、一张球员表和一段文字解读。

### 4.2 功能需求

**FR1 比赛查询。** 用户输入球队名和可选的赛事关键词，系统按球队筛选比赛索引，按日期降序返回比赛列表。赛事关键词采用大小写不敏感的子串匹配，留空表示不限赛事。

**FR2 球队名容错。** 用户可能只记得简称（barca）、拼错（barcelna）或者漏掉重音符号（Atletico Madrid）。系统需要把这类输入尽量对应到索引中的规范队名；无法唯一定位时，返回候选列表供用户选择，而不是在几支球队之间猜。

**FR3 输入补全。** 球队名输入框在用户输入时给出候选队名，支持键盘上下键选择。

**FR4 一键分析。** 用户选定比赛和球队后，系统完成数据获取、指标计算、绘图和解读生成，并返回全部结果。首次分析某场比赛需要下载数据，已缓存过的比赛直接读取本地数据。

**FR5 图形展示。** 系统展示传球网络图、射门分布图和活动热力图。传球网络图以球员平均站位为节点位置，节点大小表示传球次数，连线粗细表示两名球员之间的传球频次；射门分布图区分进球与未进球；活动热力图表示全队触球位置的密度。

**FR6 统计展示。** 系统以表格形式给出球队与对手的统计对比，以及综合评分前 5 名球员的数据。

**FR7 自动解读。** 系统调用大语言模型，按固定结构生成中文战术分析。

**FR8 降级运行。** 模型不可用或输出不合格时，系统回退到本地已保存的解读结果；网络不可用时，系统仍能基于本地缓存完成分析。系统还提供一个不依赖服务器和网络的离线静态演示包。

### 4.3 非功能需求

**NFR1 数值准确。** 所有展示的统计数字必须由程序计算得到，且每个指标的口径在代码中有明确出处，不使用大语言模型生成的数字。

**NFR2 结果可复现。** 同一场比赛、同一支球队的分析结果应当一致，重复分析不产生不同的数字。

**NFR3 部署简单。** 系统应当能在没有图形界面的服务器上运行，并尽量缩短从获取代码到可用界面的步骤。

**NFR4 负载可控。** 分析属于重操作，需要限制单位时间内单个客户端的请求次数，防止误用或恶意刷取。

**NFR5 可测试。** 关键口径（如射正分类、核心球员评分公式）应当有对应的自动化测试，改动代码后能快速确认口径没有走样。

**NFR6 数据合规。** 使用开放数据时标注数据来源与许可，不用于商业用途。

### 4.4 用例描述

主用例"完成一次单场比赛分析"的流程如下：

1. 用户输入球队名，系统返回候选队名（可选）；
2. 用户确认球队名并可选填写赛事关键词，系统返回比赛列表；
3. 用户选择一场比赛，填写或保留默认的分析提示词；
4. 用户点击分析，系统校验参数，按 match_id 读取缓存或回源下载数据；
5. 系统完成指标计算与绘图，把统计结果交给模型生成解读；
6. 系统校验模型输出，通过则返回结果，不通过则纠错重试一次，仍不通过则回退到缓存；
7. 前端展示比分、三张图、统计对比表、核心球员表和解读文本，并标注结果来源。

异常流程包括：球队名不在该场比赛中（返回参数错误提示）；比赛数据下载失败（尝试本地缓存，失败则提示错误）；模型超时或不可用（回退到缓存结果）；请求频率超过限制（返回限流提示）。

## 第五章 系统设计

### 5.1 总体架构

系统按职责分成四层，自下而上依次是数据层、分析层、服务层和展示层。

数据层负责把 StatsBomb 开放数据取到本地并按比赛隔离，对外只提供"给我 match_id，还你事件数据框和比赛元信息"这一件事。分析层在拿到数据框后计算指标并绘制图形，输出一份统计摘要和三个图对象。服务层把分析层的能力包装成 HTTP 接口，并加上参数校验、限流、缓存写入和降级处理。展示层是浏览器中的静态页面，只通过服务层接口取数据，不直接接触数据文件。

分层的实际收益在于替换成本。分析层不依赖服务层，命令行入口和 Streamlit 页面可以复用同一套分析函数，FastAPI 服务也是直接调用它；展示层改版不需要动统计口径；数据源如果要换成别家提供方，只需要改数据层的取数实现。

### 5.2 模块划分

项目的模块划分与目录结构对应，主要模块见表 5-1。

表 5-1 主要模块与职责

| 模块 | 位置 | 职责 |
| --- | --- | --- |
| 数据源 | src/data_source.py | 按 match_id 读缓存或回源下载，原子写入缓存 |
| 数据加载 | src/data_loader/statsbomb_loader.py | 读取事件 JSON 并展开为 DataFrame |
| 事件清洗 | src/preprocessing/event_cleaner.py | 过滤传球事件，解析起终点坐标 |
| 传球网络 | src/analysis/pass_network.py | 计算球员平均站位与传球关系边 |
| 射门提取 | src/analysis/shot_map.py | 提取射门事件并标记进球 |
| 位置提取 | src/analysis/heatmap.py | 提取全队触球坐标 |
| 统计摘要 | src/analysis/summary.py | 计算全部统计指标，输出摘要 JSON |
| 分析管线 | src/pipeline.py | 串联清洗、分析、绘图与报告，返回结果对象 |
| 可视化 | src/visualization/ | 球场、传球网络、射门分布、热力图绘制 |
| 模型接入 | src/llm/client.py | 调用 OpenAI 兼容接口并管理超时与重试 |
| 提示词与校验 | src/llm/prompts.py | 组装消息、约束模型、校验输出 |
| 服务端 | app/main.py | 提供 REST 接口、限流与降级 |
| 球队匹配 | app/team_matcher.py | 队名归一化、别名与模糊匹配 |
| 前端 | web/ | 静态页面与交互脚本 |
| 运维脚本 | scripts/ | 数据预置、离线包导出、离线自检 |

### 5.3 数据流

一次分析的完整数据流如下：

```
用户选择球队与比赛
        │  POST /api/analyze {match_id, team_name, prompt}
        ▼
  参数校验（比赛 ID、队名是否在本场、提示词长度）
        ▼
  取数：data/cache/{match_id}/ 命中则读本地，
        未命中则按索引中的赛事信息回源下载并写入缓存
        ▼
  json_normalize 展开事件 → DataFrame
        ▼
  ┌───────────────┬────────────────┬──────────────────┐
  │ 传球事件清洗   │ 射门事件提取    │ 全队触球位置提取  │
  └───────────────┴────────────────┴──────────────────┘
        ▼
  传球网络（站位 + 边） / 三张图 / 统计摘要 JSON
        ▼
  摘要 JSON + 用户提示词 → 大语言模型 → 中文解读
        ▼
  输出校验（结构、字数、数字一致性）→ 通过 / 纠错重试 / 回退缓存
        ▼
  响应：summary + 三张图 URL + narrative + 来源标记 + 耗时
```

### 5.4 缓存与命名空间设计

同一台机器上可能先后分析多场比赛，如果所有场次共用一组输出文件，后一次分析会覆盖前一次。系统为此采用按 match_id 命名的缓存目录：

```
data/cache/{match_id}/
├── events.json          原始事件数据
├── matches.json         本场元信息
├── lineups.json         双方阵容
├── summary.json         统计摘要（Schema v2）
├── narrative.json       中文解读及其来源标记
└── figures/
    ├── pass_network.png
    ├── shot_map.png
    └── heatmap.png
```

上述八个文件在项目中被称为"七件套"（三份原始 JSON、一份摘要、一份解读、三张图）。离线自检脚本正是按这份清单逐项检查缓存完整性的。

写入采用"先写临时文件再原子替换"的方式，避免多个进程同时写同一文件时读到半截内容。实现上先用 tempfile 在目标目录创建临时文件，写入完成后再用 os.replace 覆盖目标文件；os.replace 在同一文件系统内是原子操作，中途失败不会留下损坏的目标文件。

缓存目录之外还有一份比赛索引 data/match_index.json，由下载脚本维护，记录 match_id 对应的赛事编号、赛季编号、对阵双方、比分和日期。索引的作用有两个：回源下载 matches 文件时需要用赛事与赛季编号拼出 URL；查询比赛列表时不需要下载任何比赛数据，读索引即可。

### 5.5 统计摘要结构

系统对外输出的统计结果统一收敛成一份摘要 JSON（项目内称 Schema v2）。摘要分成七个部分：比赛元信息 match、分析球队 focus_team、对手 opponent、本队统计 team、对手统计 opponent_team、战术风格 style、进攻偏好 attack_preference，以及球员相关的 core_players、players、shot_list。各部分的字段与口径见表 5-2 至表 5-5。

表 5-2 team 与 opponent_team 字段

| 字段 | 口径 |
| --- | --- |
| goals | 进球数，射门结果等于 Goal 的事件数 |
| shots / shots_on_target | 射门数；射正数为射门结果属于 {Goal, Saved, Post} 的事件数 |
| passes / passes_completed / pass_accuracy_pct | 传球数；传球结果为空视为成功；成功数除以总数 |
| possessions / possession_share_pct | 按 possession 字段去重后本队控球的段数；占双方控球段总数的百分比 |
| final_third_passes | 传球终点 x ≥ 80 的次数 |
| box_entries | 传球终点或带球终点落入禁区的次数 |
| pass_edges | 传球网络中不同（传球人，接球人）组合的数量 |

表 5-3 style 字段

| 字段 | 口径 |
| --- | --- |
| formation | 阵型编号取众数后格式化为 4-3-3 形式 |
| avg_pass_length | 传球距离均值（码） |
| long_ball_ratio_pct | 传球距离 ≥ 35 码的传球占比 |
| passes_per_possession | 传球数除以控球段数 |
| press_events_opp_third | 防守类事件（Pressure、Ball Recovery、Interception、Duel、Block）中起点 x ≥ 80 的次数 |

表 5-4 attack_preference 字段

| 字段 | 口径 |
| --- | --- |
| left_pct / center_pct / right_pct | 进攻事件（Pass、Carry、Shot）起点 y 落在 < 26.7、26.7～53.3、> 53.3 三个区间的占比，三项之和为 100.0 |
| crosses / through_balls | pass.cross 与 pass.through_ball 为真的传球次数 |
| avg_shot_distance | 射门点到球门中心 (120, 40) 的欧氏距离均值 |
| shots_inside_box / shots_outside_box | 射门起点是否落在禁区（x ≥ 102 且 18 ≤ y ≤ 62）内 |

表 5-5 core_players 字段与评分公式

| 字段 | 口径 |
| --- | --- |
| score | goals×5 + key_passes×3 + shots×1 + network_degree×0.5 + passes×0.05，保留一位小数 |
| key_passes | pass.shot_assist 或 pass.goal_assist 为真的传球次数 |
| touches | 该球员的非元事件数（剔除换人、半场、阵型调整等不产生触球的记录） |
| network_degree | 该球员在传球网络中连接的不同队友数 |
| duels_won | 对抗结果属于 {Success In Play, Success Out, Won} 的次数 |
| interceptions | Interception 类型事件数 |

核心球员取综合分前 5 名，分数相同时按传球数降序、再按姓名排序，保证排序稳定。shot_list 则逐脚列出射门的时间、球员、坐标、结果与是否进球，为射门分布图提供数据。

口径集中写在 src/analysis/summary.py 的常量区，例如长传阈值、禁区范围、三分区边界、射正与对抗成功的取值集合。这样做的好处是口径只在一处定义，后续调整不需要在多个函数里搜索。

### 5.6 接口设计

服务端提供五个接口，见表 5-6。除健康检查与图片接口外，其余接口都做了参数范围校验，非法参数统一返回 400。

表 5-6 接口一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/health | 返回服务状态与模型是否已配置 |
| GET | /api/teams?q=&limit= | 返回候选队名，供输入框补全；q 为空时返回热门球队 |
| GET | /api/matches?team=&competition=&limit= | 按球队与赛事筛选比赛，按日期降序返回 |
| POST | /api/analyze | 执行分析，返回摘要、三张图 URL、解读文本与耗时 |
| GET | /api/figure/{match_id}/{name}.png | 返回已生成的 PNG 图，图名限定在三个白名单名称内 |

分析接口的响应中包含 narrative_source 字段，取值 live 或 cache，分别表示解读由模型实时生成或来自本地缓存。前端据此显示"实时分析"或"离线缓存结果"的徽标：当模型不可用而系统退回缓存时，用户能看出这一情况，而不是把缓存结果当作刚刚生成的输出。

### 5.7 降级设计

系统的降级分三个层次。

第一层是数据降级。分析时优先读本地缓存，读到就直接用；网络请求设置了连接 5 秒、读取 15 秒的显式超时，不会无限等待。

第二层是模型降级。模型调用失败、超时或输出校验不通过时，系统读取该场比赛已保存的 narrative.json，以"缓存"来源返回结果，保证页面仍能出完整内容。

第三层是环境降级。离线静态演示包把页面、样式、脚本、比赛数据和图片打成一个目录，内联 CSS 与 JavaScript，比赛数据直接写在页面里，图片用相对路径引用。把整个目录拷到任意一台有浏览器的电脑上双击打开即可演示，不需要服务器和网络。

## 第六章 系统实现

### 6.1 数据获取与缓存

数据层的关键在于"同一场比赛只下载一次"以及"下载失败要有明确的错误信息"。URL 模板取自 statsbombpy 的 OPEN_DATA_PATHS，只替换基址，但下载本身用 requests 直接发起，并显式设置超时——这一点与直接调用库接口不同，目的是让超时可控。

```python
# src/data_source.py
REQUEST_TIMEOUT = (5, 15)


def _http_get_json(url, match_id):
    """用 requests 直连下载 JSON，失败时抛出含 match_id 与 URL 的明确异常。"""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise DataSourceError(
            f"下载失败 match_id={match_id} url={url}: {type(exc).__name__}: {exc}"
        ) from exc
```

缓存写入用临时文件加原子替换，避免并发或中断产生半截文件：

```python
# src/data_source.py
def _atomic_write_json(path, data):
    """先写临时文件再原子替换，避免并发进程写坏同一文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix='.tmp-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
```

对外的取数入口只有 ensure_match_data 一个函数：命中缓存时读三份 JSON 并展开成数据框，未命中时按索引里的赛事信息回源下载、写缓存、再展开。调用方（分析管线、服务端）不需要关心数据来自本地还是网络。

### 6.2 事件清洗

清洗环节只做一件事：把传球事件挑出来，把起终点坐标从列表里取出来。

```python
# src/preprocessing/event_cleaner.py
def clean_pass_events(df):
    """
    提取并清洗传球事件
    """
    passes = df[df['type.name'] == 'Pass'].copy()

    # 起点坐标
    passes['x'] = passes['location'].apply(lambda x: x[0])
    passes['y'] = passes['location'].apply(lambda x: x[1])

    # 终点坐标（判断传球是否有落点）
    passes['end_x'] = passes['pass.end_location'].apply(
        lambda x: x[0] if isinstance(x, list) else None
    )
    passes['end_y'] = passes['pass.end_location'].apply(
        lambda x: x[1] if isinstance(x, list) else None
    )

    passes = passes.dropna(subset=['end_x', 'end_y'])

    return passes
```

这里用 isinstance 判断而不是直接取下标，是因为部分传球事件没有终点字段，直接取下标会抛异常。清洗后的表下游会用到三次：传球网络、统计摘要中的传球指标、进攻三区传球和禁区进入，因此统一由这一个函数产出，避免各处重复解析坐标。

### 6.3 传球网络

传球网络的数据分两部分：节点和边。节点是球员的平均站位，用该球员所有传球的起点坐标均值表示；边是两名球员之间的传球次数。

```python
# src/analysis/pass_network.py
def build_pass_network(passes, team_name):
    """
    构建传球网络所需的数据
    """
    team_passes = passes[passes['team.name'] == team_name]

    # 球员平均站位
    avg_pos = (
        team_passes
        .groupby('player.name')
        .agg(
            x=('x', 'mean'),
            y=('y', 'mean'),
            pass_count=('id', 'count')
        )
        .reset_index()
    )

    # 传球关系
    edges = (
        team_passes
        .groupby(['player.name', 'pass.recipient.name'])
        .size()
        .reset_index(name='count')
    )

    return avg_pos, edges
```

用平均站位而不是平均触球位置表示节点，是网络图常见的做法：它反映球员在传球活动中的大致位置，受个人带球和抢断的干扰较小。绘图时节点大小按传球次数缩放，边宽按传球次数缩放，读者从图上一眼能看出谁是传球枢纽、哪条连线最频繁。

### 6.4 射门提取

射门提取按照事件类型和球队过滤，并把射门结果折算成布尔值，供绘图时区分颜色。

```python
# src/analysis/shot_map.py
def extract_shots(df, team_name):
    """
    提取某球队的射门事件
    """
    shots = df[
        (df['type.name'] == 'Shot') &
        (df['team.name'] == team_name)
    ].copy()

    shots['x'] = shots['location'].apply(lambda x: x[0])
    shots['y'] = shots['location'].apply(lambda x: x[1])

    shots['is_goal'] = shots['shot.outcome.name'] == 'Goal'

    return shots
```

射正的口径与这里不同：绘图只需要区分"进球"和"未进球"，而统计摘要里的射正还要包含被扑出和中柱两种情况，因此两者的判断写在各自的位置，不做合并。

### 6.5 活动热力数据

热力图使用全队所有带坐标的事件，不限于传球和射门。

```python
# src/analysis/heatmap.py
def extract_positions(df, team_name):
    """
    提取球队所有事件的坐标
    """
    events = df[df['team.name'] == team_name].copy()

    events['x'] = events['location'].apply(
        lambda x: x[0] if isinstance(x, list) else None
    )
    events['y'] = events['location'].apply(
        lambda x: x[1] if isinstance(x, list) else None
    )

    events = events.dropna(subset=['x', 'y'])

    return events
```

取点范围是全部事件而不是传球，原因在于热力图要表达的是"球队在哪里活动"，传球点只覆盖了一部分触球行为。这里同时剔除了没有坐标的事件，因为并非所有事件都带位置信息。

### 6.6 统计摘要实现

统计摘要模块是所有口径的落点。文件开头集中定义了口径常量：

```python
# src/analysis/summary.py
# 球门中心（StatsBomb 坐标，单位：码）
GOAL_CENTER = (120.0, 40.0)

# 禁区（18 码区）：x>=102 且 18<=y<=62（任务书口径）
BOX_X_MIN = 102.0
BOX_Y_MIN = 18.0
BOX_Y_MAX = 62.0

# 进攻三区：x>=80（任务书口径）
FINAL_THIRD_X = 80.0

# 长传阈值：pass.length >= 35 码（StatsBomb 常用长传定义，源码字段 pass.length 单位为码）
LONG_BALL_THRESHOLD = 35.0

# 左右中三分区边界：<26.7 左路，26.7~53.3 中路，>53.3 右路（任务书口径）
LEFT_Y_MAX = 26.7
RIGHT_Y_MIN = 53.3

# 射正归类：归为射正的取值：Goal（进球）、Saved（被扑）、Post（中柱，即 Saved to Post）。
SHOT_ON_TARGET_OUTCOMES = {'Goal', 'Saved', 'Post'}

# 对抗成功归类：Success In Play / Success Out / Won（Won 为空中对抗获胜）。
DUEL_WON_OUTCOMES = {'Success In Play', 'Success Out', 'Won'}

# 前场压迫类防守事件：Pressure / Ball Recovery / Interception / Duel / Block 均属于防守行为。
PRESS_TYPES = {'Pressure', 'Ball Recovery', 'Interception', 'Duel', 'Block'}

# 进攻事件类型：左右中占比只统计 Pass + Carry + Shot（任务书口径）
ATTACK_TYPES = {'Pass', 'Carry', 'Shot'}

# 非触球元事件：计算 touches 时剔除（换人/阵型/半场/伤停等不产生触球）
META_TYPES = {
    'Starting XI', 'Half Start', 'Half End', 'Tactical Shift',
    'Player On', 'Player Off', 'Substitution', 'Injury Stoppage',
}
```

射正、对抗成功、压迫类事件这三组取值集合来自对实际数据的枚举。数据集里 shot.outcome.name 的取值包括 Goal、Saved、Blocked、Off T、Wayward、Post 等，其中被扑出和中柱都属于"射向球门"的行为，因此归入射正；Blocked 和 Off T 不计入。duel.outcome.name 的取值包括 Success In Play、Success Out、Won、Lost In Play、Lost Out，前三者计为对抗成功。

球队统计由 _team_stats 统一计算，控球次数按 possession 字段去重后归属到控球方：

```python
# src/analysis/summary.py
def _possession_counts(events_df):
    """按 possession 字段去重后，用 possession_team.name 计数双方控球次数。"""
    # 每个 possession 序号代表一段连续控球，去重后按控球方统计
    poss = events_df.drop_duplicates(subset=['possession'])
    counts = poss['possession_team.name'].value_counts()
    return counts
```

这样处理之后，"控球次数"指的是控球段数，而不是控球时间。摘要里还同时给出传球数，用传球数除以控球段数可以得到"每段控球传球多少次"，这个比值比控球时间更容易从事件数据里直接算出，也更能反映球队的传递节奏。

核心球员评分把进球、关键传球、射门、传球网络连接度和传球量加权求和，取前 5 名：

```python
# src/analysis/summary.py
def _core_players(rows):
    """core_players：综合分前 5 名。

    score = goals*5 + key_passes*3 + shots*1 + network_degree*0.5 + passes*0.05
    """
    scored = []
    for r in rows:
        score = (
            r['goals'] * 5
            + r['key_passes'] * 3
            + r['shots'] * 1
            + r['_network_degree'] * 0.5
            + r['passes'] * 0.05
        )
        # 组装该球员的字段：name / score / passes / pass_accuracy_pct / ...
        scored.append({...})
    scored.sort(key=lambda r: (-r['score'], -r['passes'], r['name']))
    return scored[:5]
```

公式里的权重是人为设定的：进球权重最高，关键传球次之，射门、网络连接度和传球量依次降低。它的作用是让前锋和中场组织者都能进入榜单，而不是让传球最多的后卫刷满分数。排序时用传球数和姓名作为并列时的次级键，保证同样的数据每次运行得到同样的顺序。

摘要中所有数值都转成原生 Python 类型（int、float、bool、str），这是为了让 json.dumps 可以直接序列化，也避免把 numpy 类型写进缓存文件后在别的进程里反序列化出错。浮点指标统一保留一位小数。

### 6.7 可视化实现

球场对象由 mplsoccer 的 Pitch 创建，坐标类型指定为 statsbomb，因此事件坐标可以直接使用：

```python
# src/visualization/pitch.py
from mplsoccer import Pitch


def create_pitch():
    pitch = Pitch(
        pitch_type='statsbomb',
        pitch_color='white',
        line_color='black'
    )
    fig, ax = pitch.draw(figsize=(10, 7))
    return pitch, fig, ax
```

传球网络图先画点再画线，点的面积与传球次数成正比，线的宽度与传球次数成正比：

```python
# src/visualization/plot_utils.py
def draw_pass_network(pitch, ax, avg_pos, edges):
    # 画球员点
    pitch.scatter(
        avg_pos['x'],
        avg_pos['y'],
        s=avg_pos['pass_count'] * 10,
        ax=ax,
        color='red',
        zorder=3
    )

    # 球员名字
    for _, row in avg_pos.iterrows():
        ax.text(row['x'], row['y'], row['player.name'],
                ha='center', va='center', fontsize=8)

    # 画传球线
    for _, row in edges.iterrows():
        p1 = avg_pos[avg_pos['player.name'] == row['player.name']]
        p2 = avg_pos[avg_pos['player.name'] == row['pass.recipient.name']]

        if p1.empty or p2.empty:
            continue

        pitch.lines(
            p1['x'], p1['y'],
            p2['x'], p2['y'],
            lw=row['count'] / 2,
            ax=ax,
            color='blue',
            alpha=0.6,
            zorder=2
        )
```

画线之前要先确认两名球员都在平均站位表里。出现这种情况的原因是接球人可能是对方球员（传球被断），也可能是被换下的球员，这类边没有对应的节点，会被跳过，避免程序报错。

射门分布图用两种颜色区分进球与未进球，点的大小也略有差别：

```python
# src/visualization/shot_plot.py
def draw_shot_map(pitch, ax, shots):
    # 非进球
    pitch.scatter(
        shots[~shots['is_goal']]['x'],
        shots[~shots['is_goal']]['y'],
        ax=ax,
        s=60,
        color='blue',
        alpha=0.6,
        label='Shot'
    )

    # 进球
    pitch.scatter(
        shots[shots['is_goal']]['x'],
        shots[shots['is_goal']]['y'],
        ax=ax,
        s=100,
        color='red',
        edgecolors='black',
        label='Goal'
    )

    ax.legend()
```

热力图用核密度估计把散点转换成功率密度，填充色使用红色渐变：

```python
# src/visualization/heatmap_plot.py
def draw_heatmap(pitch, ax, events):
    pitch.kdeplot(
        events['x'],
        events['y'],
        ax=ax,
        fill=True,
        levels=100,
        cmap='Reds'
    )
```

三张图都由分析管线统一生成并保存为 300 dpi 的 PNG。分析管线返回的是 matplotlib 的 Figure 对象而不是文件路径，命令行入口负责保存到 outputs 目录，服务端负责保存到缓存目录，两处复用同一份绘图逻辑。

### 6.8 模型接入与输出校验

防止模型编造数据是本系统在实现上花力气最多的地方，做法分三步。

第一步是把要求写进 system 提示词，明确禁止引入外部知识，并规定输出结构：

```python
# src/llm/prompts.py
SYSTEM_PROMPT = (
    "你是足球战术分析师。你只能使用用户提供的 summary JSON 中的数字进行分析，"
    "禁止引入任何外部知识，禁止编造、推测或补充 JSON 中不存在的数据。"
    "如果用户询问的指标（如 xG、预期进球）在 JSON 中不存在，必须明确回答“数据不足”，"
    "并说明 JSON 中没有该字段，绝不能编造数字。"
    "你必须使用中文输出，并严格按以下五段结构撰写，每段以标题“结论”“战术风格”"
    "“进攻偏好”“核心球员表现”“建议”开头。"
    "每一段中引用的任何数字必须与 JSON 中的数字完全一致。"
    "全文总字数不得超过 800 字。"
)
```

提示词只约束模型的行为，不能保证模型遵守。第二步是把约束变成程序可检查的条件。校验函数检查三件事：五个段落标题是否齐全、总字数是否超过 800、输出中出现的小数是否都能在摘要 JSON 里找到。

```python
# src/llm/prompts.py
def find_foreign_decimals(text: str, summary: dict) -> list:
    """返回输出文本中出现、但 JSON 中不存在的小数 token（用于防幻觉校验）。

    只校验带小数点的数字，避免把日期、段号等整数误判为违规。
    """
    allowed = set()
    _collect_numbers(summary, allowed)
    foreign = []
    for token in re.findall(r"\d+\.\d+", text or ""):
        value = float(token)
        if not any(abs(value - item) < 1e-9 for item in allowed):
            foreign.append(token)
    return foreign
```

只校验带小数点的数字是有意的：日期、分钟数这类整数在正文里出现是正常的，如果一并校验会大量误报；而统计指标里的小数（传球成功率、控球份额、射门距离等）本来就来自摘要，出现摘要之外的小数，基本可以判定是模型自己算的或者编的。

第三步是校验失败后的处理。服务端在第一次校验不通过时，把具体问题追加到提示词里，让模型重写一次；仍然不通过就改用本地缓存的解读。

```python
# app/main.py
    problems = validate_output(narrative, summary)
    if problems:
        # 追加一句纠错提示重新调用一次
        retry_prompt = (
            prompt
            + "\n\n注意：上次输出存在以下问题，请严格按五段结构并使用 JSON 中的数字逐项修正后重新输出：\n"
            + "\n".join(f"- {problem}" for problem in problems)
        )
        try:
            narrative = llm_analyze(summary, retry_prompt)
        except LLMUnavailable as exc:
            cached = _read_cache_fallback(match_id, team_name, t0)
            if cached is not None:
                return cached
            return JSONResponse(status_code=502, content={"detail": f"模型不可用: {exc}"})
```

模型客户端自己管理超时与重试，不使用 SDK 自带的重试，原因是需要在总耗时上限内控制重试次数：

```python
# src/llm/client.py
        for attempt in range(max_retries + 1):
            # 预留 0.2s 给超时异常的传播开销，确保在 LLM_TIMEOUT 内抛出
            remaining = deadline - time.monotonic() - 0.2
            if remaining <= 0:
                break
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    timeout=remaining,
                )
                content = response.choices[0].message.content
                break
            except Exception as exc:
                last_exc = exc
```

异常信息在抛出前会把 API Key 替换成 ***，避免密钥随错误信息写进日志或返回给前端。

### 6.9 服务端实现

服务端按"校验—取数—计算—调用模型—校验输出—返回"的顺序组织，每一步的失败都有对应的响应。

参数校验分两层。请求体的类型与取值范围由 Pydantic 模型约束；球队是否真的在这场比赛里，则由服务端在拿到比赛索引后比对。比对时先做归一化，允许大小写、重音和标点上的差异，但必须换回索引里的规范队名——否则后续按队名过滤事件会一条都匹配不到。

```python
# app/main.py
        if normalize_name(team_name) == normalize_name(home):
            team_name = home
        elif normalize_name(team_name) == normalize_name(away):
            team_name = away
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": f"参数非法: 球队 '{team_name}' 不在本场比赛（{home} vs {away}）"
                },
            )
```

球队名匹配本身是一个独立模块。它把队名做归一化处理——用 NFKD 分解去掉重音符号，转小写，把标点和 & 之类的符号换成空格，压缩连续空格——再按分档规则打分，分数越高越可信：

| 分数 | 匹配方式 | 例子 |
| --- | --- | --- |
| 100 | 归一化后完全一致 | Atletico Madrid → Atlético Madrid |
| 96 | 命中别名表 | barca → Barcelona |
| 90 | 整名前缀 | barce → Barcelona |
| 84 | 队名中某个词的前缀 | united → Manchester United |
| 78 | 多词查询，每个词都对上某个词的前缀 | man united → Manchester United |
| 74 | 子串出现 | celona → Barcelona |
| 45～60 | 编辑距离相似度 | 拼写错误的输入 |

只有分数达到阈值且明显领先第二名时才会自动采用该队名，否则只把它作为候选项交给前端。带女足、预备队后缀（WFC、Women、Ladies 等）的队名会被降权 12 分，这样用户输入 barce 时排在前面的通常是 Barcelona 而不是 Barcelona WFC。这套规则解决的问题是索引里有近四千场比赛、涉及大量队名变体，直接做精确匹配会让用户频繁查不到结果。

分析接口按客户端 IP 限流，默认每分钟 60 次，超过后返回 429 并给出中文提示。限流只加在这一个接口上，其余接口是读索引或读缓存文件，开销小。

前端页面与图片接口统一加了 no-cache 响应头。浏览器每次会向服务端确认一次，内容没变时返回 304，改动前端代码或重新分析之后，用户不会再看到上一次的旧文件。

### 6.10 前端实现

前端没有使用框架，只有 index.html、style.css 和 app.js 三个文件。这样做是因为页面本身的状态很少：一支球队、一场比赛、一次分析结果，用框架反而增加了构建环节。

页面的交互按四步组织，与用户的心理顺序一致：输入球队名、可选填赛事关键词、选择比赛、填写分析提示词，最后点分析。球队名输入框带自动补全：输入停止 200 毫秒后才发请求，避免每敲一个字符都请求一次；候选列表支持键盘上下键移动，越界时循环；输入法组字期间不触发补全，否则中文输入会被打断。

结果区按信息的重要程度排列：先显示结果来源徽标和耗时，再是比分牌，然后是三张图，之后是解读文本，最后是团队统计对比表和核心球员表。来源徽标根据 narrative_source 显示"实时分析"或"离线缓存结果"，用户能看出这次结果是模型刚生成的还是从缓存取回的。

团队统计对比表固定列出十项指标：

```javascript
// web/app.js
const STAT_ROWS = [
  { key: "goals", label: "进球" },
  { key: "shots", label: "射门" },
  { key: "shots_on_target", label: "射正" },
  { key: "passes", label: "传球" },
  { key: "pass_accuracy_pct", label: "传球成功率%" },
  { key: "possessions", label: "控球次数" },
  { key: "possession_share_pct", label: "控球份额%" },
  { key: "final_third_passes", label: "进攻三区传球" },
  { key: "box_entries", label: "禁区进入" },
  { key: "pass_edges", label: "传球网络边数" },
];
```

样式表按 860 像素设置断点，窄屏下三张图改为纵向排列，手机浏览器可以正常演示。

### 6.11 预置、离线包与自检

scripts 目录下有三个运维脚本。

prefetch.py 负责预置演示比赛。它按比赛逐个检查缓存是否齐备，缺什么补什么：缺少原始 JSON 就依次尝试多个下载源（本地缓存、jsDelivr 镜像、GitHub API、raw.githubusercontent），缺少摘要和三张图就用分析管线重新生成，narrative.json 已存在则跳过，不重复调用模型。脚本预置的比赛包括 3749552（Manchester United 0-0 Arsenal，2003 英超）、18245（Real Madrid 3-1 Liverpool，2018 欧冠决赛）和 3773661（Barcelona 5-2 Getafe，2021 西甲）。

export_static_demo.py 负责导出离线静态演示包。它把 CSS 与 JavaScript 内联进页面，把比赛数据和表格直接写成 JSON 嵌在页面里，把三张图复制到 figures/{match_id}/ 下按相对路径引用。生成的目录里放一个 .ftas-demo-static 标记文件，重复运行时据此判断该目录是本工具生成的，可以安全清理，避免误删用户自己的目录。

smoke_test.py 是离线自检脚本，不访问网络、不调用模型、不读取密钥。它对 data/cache 下的每场比赛检查七件套是否齐备、文件是否为空，再用本地数据重新构建一次摘要，确认口径代码在改动后仍能跑出结果。任意一场失败则进程退出码为 1。

### 6.12 部署实现

Dockerfile 基于 python:3.11-slim，安装 fonts-noto-cjk 中文字体和 libgomp1（mplsoccer 的依赖），先复制 requirements.txt 安装依赖再复制代码，以便充分利用镜像层缓存。容器内创建一个 uid 1000 的非 root 用户运行服务，密钥不设默认值、只在运行时通过环境变量注入，避免写进镜像层。

```dockerfile
# Dockerfile
RUN sed -i "s|http://deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends fonts-noto-cjk libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -i ${PIP_INDEX_URL}
```

docker-compose 把 ./data/cache 挂载为数据卷，容器重启后缓存内容还在；restart 策略设为 unless-stopped，服务器重启后容器自动恢复。模型服务地址、模型名、超时、重试次数、限流额度、提示词长度上限都通过环境变量注入，改配置不需要重新构建镜像。

常用运维命令（查看状态、查看日志、重启、重建）与故障排查表写在 deploy/README.md 中，页面打不开、限流、模型未配置、图表中文显示方块等常见问题都有对应的处理步骤。

## 第七章 系统测试与运行结果

### 7.1 测试方法

系统采用三种方式验证。

一是单元测试。用 pytest 对不依赖网络和外部服务的部分做自动化测试，覆盖统计口径、提示词约束与输出校验、球队名匹配三块。这部分测试在每次改动后运行，用来确认口径没有走样。

二是离线自检。用 scripts/smoke_test.py 对 data/cache 下的每一场缓存比赛做完整性检查，再用本地数据重新构建一次统计摘要，确认从原始数据到摘要的链路在当前代码下仍然走得通。自检不访问网络、不调用模型、不读取密钥。

三是手工端到端验证。按用户的实际操作顺序，从输入球队名开始，走完查询、分析、查看结果的完整流程，并在模型不可用、网络中断等条件下验证降级行为。

### 7.2 单元测试

测试文件共三个，合计 29 个用例，全部通过，总耗时 0.62 秒。

表 7-1 单元测试覆盖情况

| 测试文件 | 用例数 | 覆盖内容 |
| --- | --- | --- |
| tests/test_llm_prompts.py | 10 | 系统提示词包含硬约束；system 与 user 消息分离；用户提示词截断到 2000 字符；合法输出通过校验；缺段落、超字数、外来小数被检出；xG 这类不在摘要中的小数被拒绝；未配置密钥时抛出模型不可用异常 |
| tests/test_summary.py | 6 | 摘要 Schema 字段完整；射正分类正确；核心球员取前 5 且评分公式一致；左中右占比之和为 100；未知球队抛出参数错误；摘要可 JSON 序列化 |
| tests/test_team_matcher.py | 13 | 队名归一化去除重音与大小写差异；女足后缀识别；完全匹配返回规范队名且不被降权；简称走别名表；前缀匹配不选到女足队；歧义输入只返回候选不自动选定；拼写错误仅作为候选；未知队名不返回结果；同分时热门队优先；带后缀队名降权但保留在候选里；空查询返回热门队；索引中的坏记录被跳过 |

其中三个用例针对的是容易出错的地方。核心球员评分公式的用例直接比对手工计算的分值，改动权重时会立刻失败；左中右占比的用例断言三项之和等于 100.0，避免四舍五入造成的偏差被忽略；外来小数的用例断言摘要中没有出现的值会被判为违规，这是防幻觉机制的底线。

### 7.3 离线自检结果

对 data/cache 下的六场比赛运行离线自检，结果全部通过，如表 7-2 所示。

表 7-2 离线自检结果

| match_id | 比赛 | 分析球队 | 事件数 | 参与传球球员数 | 结果 |
| --- | --- | --- | --- | --- | --- |
| 18245 | Real Madrid 3-1 Liverpool（2018 欧冠决赛） | Liverpool | 3497 | 13 | PASS |
| 3749552 | Manchester United 0-0 Arsenal（2003 英超） | Manchester United | 3572 | 12 | PASS |
| 3764440 | Barcelona 3-0 Elche（西甲） | Barcelona | 4160 | 16 | PASS |
| 3773377 | Barcelona 2-2 Valencia（西甲） | Barcelona | 3717 | 15 | PASS |
| 3773661 | Barcelona 5-2 Getafe（2021 西甲） | Barcelona | 4129 | 15 | PASS |
| 3802683 | Paris Saint-Germain 2-0 AS Monaco（法甲） | Paris Saint-Germain | 3838 | 15 | PASS |

总计 6 场通过、0 场失败。表中事件数是各场 events.json 解析后的事件条数，说明单场比赛的事件规模在三千余条至四千余条之间；参与传球球员数是该队传球事件中出现的球员个数，一场比赛通常有 12 到 16 人。

### 7.4 运行结果

以 3773661（Barcelona 5-2 Getafe，2021 年 4 月 22 日，西甲 2020/2021 赛季）为例，系统输出的主要指标如下。

表 7-3 巴塞罗那与赫塔菲的统计对比

| 指标 | 巴塞罗那 | 赫塔菲 |
| --- | --- | --- |
| 进球 | 4 | 1 |
| 射门 | 9 | 5 |
| 射正 | 6 | 1 |
| 传球 | 973 | 229 |
| 传球成功 | 885 | 153 |
| 传球成功率 | 91.0% | 66.8% |
| 控球段数 | 82 | 55 |
| 控球份额 | 59.9% | 40.1% |
| 进攻三区传球 | 194 | 93 |
| 禁区进入 | 44 | 27 |
| 传球网络边数 | 153 | 108 |

表 7-4 巴塞罗那的战术风格与进攻偏好

| 指标 | 数值 |
| --- | --- |
| 阵型 | 3-5-2 |
| 平均传球长度 | 17.3 码 |
| 长传占比 | 5.1% |
| 每控球段传球数 | 11.9 |
| 前场压迫事件 | 34 |
| 左路占比 | 25.2% |
| 中路占比 | 33.3% |
| 右路占比 | 41.5% |
| 传中 | 4 |
| 直塞 | 8 |
| 平均射门距离 | 15.6 码 |
| 禁区内射门 / 禁区外射门 | 7 / 2 |

表 7-5 综合评分前 5 名球员

| 姓名 | 综合分 | 传球 | 成功率 | 关键传球 | 射门 | 进球 | 触球 | 网络连接度 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lionel Andrés Messi Cuccittini | 28.9 | 59 | 79.7% | 1 | 7 | 2 | 216 | 12 |
| Antoine Griezmann | 17.1 | 33 | 90.9% | 1 | 1 | 1 | 146 | 13 |
| Sergio Busquets i Burgos | 15.4 | 108 | 96.3% | 1 | 0 | 0 | 307 | 14 |
| Frenkie de Jong | 14.9 | 98 | 91.8% | 1 | 0 | 0 | 307 | 14 |
| Ronald Federico Araújo da Silva | 13.7 | 44 | 97.7% | 0 | 1 | 1 | 134 | 11 |

三张图由本地缓存 data/cache/3773661/figures/ 提供，本次分析使用的数据与绘图代码即第六章所述实现。

![传球网络图（Barcelona 5-2 Getafe）](../../data/cache/3773661/figures/pass_network.png)

图 7-1 传球网络图

![射门分布图（Barcelona 5-2 Getafe）](../../data/cache/3773661/figures/shot_map.png)

图 7-2 射门分布图

![活动热力图（Barcelona 5-2 Getafe）](../../data/cache/3773661/figures/heatmap.png)

图 7-3 活动热力图

模型的解读输出如下（节选，五段结构完整）：

> 结论
> 本场巴塞罗那5比2战胜赫塔菲，焦点球队巴塞罗那控球率59.9%，传球973次、成功885次，传球成功率91.0%，射门9次、射正6次，进4球。赫塔菲控球率40.1%，传球229次，成功率66.8%，射门5次、射正1次、进1球。数据表明巴塞罗那在控球、传球和射门效率上全面占优。
>
> 战术风格
> 巴塞罗那采用3-5-2阵型，场均传球长度17.3，长传比例仅5.1%，每次控球传球11.9次，前场压迫事件34次。全队传球973次，远超赫塔菲的229次；最终三区传球194次，赫塔菲为93次。这体现短传控制与高位压迫结合的战术风格。
>
> ……

解读中的每个数字都与表 7-3、表 7-4 一致，没有出现摘要之外的数值。

再看 3749552（Manchester United 0-0 Arsenal，2003 年 9 月 21 日，英超 2003/2004 赛季），命令行入口生成的文字报告如下：

```
==================================================
比赛: Manchester United 0 - 0 Arsenal
日期: 2003-09-21
赛事: Premier League 2003/2004
分析球队: Manchester United
==================================================

【传球网络】
参与传球球员数: 12
传球关系(边)数: 97
传球最多: Roy Keane (75 次)

各球员传球次数:
  Roy Keane: 75
  Gary Neville: 66
  John O''Shea: 62
  Quinton Fortune Kolobea: 54
  Mikaël Silvestre: 52
  Rio Ferdinand: 48
  Ryan Giggs: 42
  Cristiano Ronaldo dos Santos Aveiro: 39
  Phil Neville: 30
  Tim Howard: 30
  Ruud van Nistelrooy: 17
  Diego Forlán Corazo: 4

【射门】
射门次数: 8
进球数: 0
```

这场比赛双方零封，曼联射门 8 次、射正 5 次、进球 0 个，阿森纳射门 7 次、射正 1 次。系统给出的传球成功率曼联 75.5%、阿森纳 78.8%，平均传球长度 22.5 码，长传占比 16.4%，与巴塞罗那那场的 17.3 码、5.1% 形成明显对照。同一套指标在不同风格的比赛里能区分出不同的打法，说明口径本身是有区分度的。

### 7.5 防幻觉验证

用一个摘要里没有的指标做验证：向系统提出"请告诉我这场比赛的预期进球 xG 是多少"。摘要 JSON 中没有 xG 字段，模型按提示词要求回答"数据不足"，并说明 JSON 中没有该字段，没有给出任何具体数值。程序侧的校验也提供了第二道防线——即使模型给出了数字，只要它不在摘要的数值集合里，就会被判为违规并触发重写或回退。

### 7.6 演示环境

系统在答辩场景下准备了三种演示形态。一是服务器实时模式，容器以完整配置启动，现场分析并调用模型；二是服务器离线模式，容器以空密钥启动，接口在模型不可用时返回本地缓存结果，页面徽标显示"离线缓存结果"；三是离线静态包，把 demo_static 目录拷入 U 盘，在有浏览器的电脑上双击 index.html 演示，不需要网络和服务器。三种形态共用同一套统计口径和前端样式，区别只在解读文本的来源。

## 第八章 总结与展望

### 8.1 工作总结

本课题完成了以下工作。

第一，搭起了一条从公开数据到战术结论的完整链路：下载并缓存 StatsBomb 事件数据，展开成表格，解析传球与射门事件，计算团队、战术风格、进攻偏好和球员四类指标，绘制传球网络、射门分布和活动热力图，并生成文字报告与中文解读。整条链路在一台普通电脑上即可运行。

第二，把统计口径固定下来。球门中心、禁区范围、进攻三区、长传阈值、左右中分区边界、射正与对抗成功的取值集合都集中定义在 src/analysis/summary.py 中，避免了同一指标在不同地方算法不一致的问题。

第三，实现了可用的系统形态。FastAPI 提供查询与分析接口，静态前端提供四步交互和结果展示，Docker 负责交付与部署，球队名模糊匹配解决了用户记不住规范队名的问题，离线包保证了网络不可用时仍能演示。

第四，对模型的编造行为做了约束。提示词限制模型只使用摘要中的数字，程序校验段落结构、字数和数字一致性，不通过则纠错重试一次，再失败则回退到缓存结果。经过这一层处理，模型输出中的数字与统计结果保持一致。

### 8.2 不足与展望

系统目前有几处明显的不足。

一是分析范围限于单场比赛，没有跨场次的趋势比较。要判断一支球队的打法是否稳定，需要把多个场次的指标放在一起看，目前的摘要结构没有为此留出位置。

二是数据来源单一。系统只接入了 StatsBomb 开放数据，比赛场次以历史赛事为主，不含实时数据；若换成其他提供方，坐标系统和字段命名都需要重新适配。

三是缺少视频与位置数据。事件数据记录了球在哪里、由谁做了什么，但没有球员位置追踪数据，因此无法计算跑动距离、阵型紧凑度这类指标，也无法把结论对应到画面上。

四是模型解读的质量依赖提示词，不同提问方式得到的分析深浅不一，目前只能保证数字准确，不能保证分析的角度足够全面。

后续可以考虑的改进方向是：增加多场比赛的对比视图；把摘要结构扩展成可跨场次聚合的形式；在摘要中补充预期进球等事件数据中可以直接得到的高阶指标；为提示词准备几套针对不同分析角度的模板。

## 参考文献

[1] ÖZGÜVEN Y M, GÖNENER U, EKEN S. A Dockerized Big Data Architecture for Sports Analytics[J]. Computer Science and Information Systems, 2022, 19(2): 957-978. DOI: 10.2298/CSIS220118010O.

[2] ZHAO S Y, MA H, PU Z Q, 等. TacEleven: Generative Tactic Discovery for Football Open Play[Z]. 预印本. 作者单位：中国科学院自动化研究所复杂系统认知与决策智能重点实验室、中国科学院大学、上海人工智能实验室、AJ Auxerre 俱乐部.

数据来源：StatsBomb Open Data，https://github.com/statsbomb/open-data ，许可 CC BY-NC-SA 4.0，仅限非商业用途。

## 附录 A 主要文件清单

```
FTAS/
├── main.py                     命令行分析入口
├── analyze.py                  交互式选赛分析入口
├── download_match.py           按 match_id 下载比赛并维护索引
├── list_matches.py             查询球队比赛列表
├── web_app.py                  Streamlit 网页版
├── app/                        FastAPI 服务（main / schemas / limiter / team_matcher）
├── web/                        静态前端（index.html / style.css / app.js）
├── src/
│   ├── data_source.py          按 match_id 缓存的取数层
│   ├── data_loader/            事件 JSON 读取
│   ├── preprocessing/          传球事件清洗
│   ├── analysis/               传球网络 / 射门 / 热力数据 / 统计摘要
│   ├── visualization/          球场与三种图形绘制
│   ├── llm/                    模型接入与提示词校验
│   ├── pipeline.py             分析管线
│   └── utils/config.py         路径配置
├── scripts/                    数据预置 / 离线包导出 / 离线自检
├── tests/                      单元测试
├── data/
│   ├── cache/{match_id}/       按比赛隔离的缓存
│   └── match_index.json        比赛索引
├── outputs/                    命令行入口的图表与报告
├── demo_static/                离线静态演示包
├── docs/                       演示脚本与本文
├── Dockerfile / docker-compose.yml
└── deploy/                     部署文档
```

## 附录 B 环境与运行说明

运行环境：Python 3.11 及以上；主要依赖为 pandas、matplotlib、mplsoccer、statsbombpy、fastapi、uvicorn、pydantic-settings、openai、slowapi、pytest。

命令行使用：

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python analyze.py
```

网页服务使用：

```bash
docker compose up -d
# 浏览器打开 http://localhost:8000
```

离线静态演示包：

```bash
.venv/bin/python scripts/export_static_demo.py
# 把整个 demo_static/ 目录拷走，双击 index.html
```

离线自检：

```bash
.venv/bin/python scripts/smoke_test.py
```

单元测试：

```bash
.venv/bin/python -m pytest -q
```
