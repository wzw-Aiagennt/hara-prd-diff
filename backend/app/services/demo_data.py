"""内置示例数据, 用于无需上传文件即可端到端演示三种判定 (需求③)。

覆盖:
  - 车速 0-80 → 0-130 km/h (新增分析)
  - ODD 新增城市匝道 (新增分析)
  - 删除夜视功能 (删减分析)
  - 仅调整提示文字文案 (完全复用)
"""

OLD_PRD = """1 概述
本文件描述自适应巡航系统(ACC)的产品需求。
系统工作车速范围为 0-80km/h。
系统配备夜视功能, 支持夜间行人识别。
驾驶员手册提示文字为: ACC 已激活。
系统运行于结构化高速道路。
前向摄像头与毫米波雷达融合感知。
2 运行条件
系统依赖车道线与前车目标进行纵向控制。
"""

NEW_PRD = """1 概述
本文件描述自适应巡航系统(ACC)的产品需求。
系统工作车速范围为 0-130km/h。
驾驶员手册提示文字为: 自适应巡航 已开启。
系统运行于结构化高速道路与城市匝道。
前向摄像头与毫米波雷达融合感知。
2 运行条件
系统依赖车道线与前车目标进行纵向控制。
"""

HARA = {
    "columns": ["asil", "c", "e", "function", "hazard_event", "id", "s", "safety_goal"],
    "record_count": 3,
    "records": [
        {"_sheet": "HARA", "_row": 2, "id": "HARA-01", "hazard_event": "夜间行人识别失效导致碰撞", "function": "夜视行人检测", "S": "S3", "E": "E3", "C": "C3", "asil": "ASIL D", "safety_goal": "避免对弱势道路使用者碰撞"},
        {"_sheet": "HARA", "_row": 3, "id": "HARA-02", "hazard_event": "高速工况下跟车距离不足导致追尾", "function": "自适应巡航", "S": "S3", "E": "E4", "C": "C2", "asil": "ASIL C", "safety_goal": "维持安全车距"},
        {"_sheet": "HARA", "_row": 4, "id": "HARA-03", "hazard_event": "提示文字与实际状态不一致误导驾驶员", "function": "HMI 显示", "S": "S1", "E": "E3", "C": "C1", "asil": "QM", "safety_goal": "状态显示准确"},
    ],
    "text": (
        "[HARA 行2] id=HARA-01; hazard_event=夜间行人识别失效导致碰撞; function=夜视行人检测; S=S3; E=E3; C=C3; asil=ASIL D; safety_goal=避免对弱势道路使用者碰撞\n"
        "[HARA 行3] id=HARA-02; hazard_event=高速工况下跟车距离不足导致追尾; function=自适应巡航; S=S3; E=E4; C=C2; asil=ASIL C; safety_goal=维持安全车距\n"
        "[HARA 行4] id=HARA-03; hazard_event=提示文字与实际状态不一致误导驾驶员; function=HMI 显示; S=S1; E=E3; C=C1; asil=QM; safety_goal=状态显示准确"
    ),
}
