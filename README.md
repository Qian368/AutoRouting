# “四步法”构建回路导线布局系统

## 项目简介
本项目是一个基于“四步法”理论的回路导线布局辅助设计工具。它允许用户在二维画布上绘制电气节点（配电箱、开关、灯具、插座等）和导管连接，并通过交互式定义受控单元，自动计算每根导管内需要穿过的导线数量和类型。

## 项目架构
```mermaid
graph TD
    Main[main.py] --> MainWindow[src.frontend.main_window]
    MainWindow --> Scene[src.frontend.canvas]
    MainWindow --> Dialogs[src.frontend.dialogs]
    MainWindow --> UnitManager[src.frontend.unit_manager]
    MainWindow --> CircuitManager[src.frontend.circuit_manager]
    MainWindow --> Calculator[src.backend.algorithms]
    
    Scene --> Models[src.backend.models]
    UnitManager --> Models
    UnitManager --> Dialogs
    CircuitManager --> Models
    Calculator --> Models
    Calculator --> NetworkX[NetworkX Graph Lib]
    
    Models --> Constants[src.backend.models (Enum)]
    MainWindow --> Messages[src.common.messages]
    UnitManager --> Messages
    CircuitManager --> Messages
```

### 模块说明
- **src/frontend**: 包含图形用户界面代码 (PyQt6)。
    - `main_window.py`: 主窗口逻辑，集成画布、工具栏、属性面板和全局快捷键。
    - `canvas.py`: 基于 `QGraphicsScene` 的绘图引擎，处理节点、连线的绘制及交互状态管理。
    - `unit_manager.py`: 单元管理对话框，负责受控/非受控单元的创建、编辑和独立编号管理。
    - `circuit_manager.py`: 回路管理器，支持多回路定义、配电箱关联及成员节点分配。
    - `dialogs.py`: 属性设置和单元定义基础对话框。
- **src/backend**: 包含核心业务逻辑。
    - `models.py`: 定义系统数据结构 (Node, Conduit, Wire, Unit, Circuit, CircuitSystem)，包含级联更新和独立自增编号算法。
    - `algorithms.py`: 实现“四步法”布线算法及基于 MST 的自动拓扑生成。
- **src/common**: 公共资源。
    - `messages.py`: 集中管理所有用户可见的文本字符串。

## 功能特性
1. **二维可视化编辑**：支持拖拽添加节点，点击建立导管连接。
2. **多级管理逻辑**：
    - **回路管理**：支持多配电箱场景，手动或自动划分节点归属。
    - **单元管理**：独立自增编号系统（受控 C-UTx / 非受控 U-UTx），支持一键自动识别插座单元。
3. **高效交互体验**：
    - **属性面板**：支持**双击编辑**节点属性（ID、标签、联数等）；展示导管内**详细导线列表**（类型、所属单元、实时电流）。
    - **参数锁定**：支持锁定新增节点的默认参数，方便连续放置同类设备。
    - **快捷操作**：按下 `Esc` 键可随时从任何模式跳转回框选模式。
4. **自动化布线计算**：严格遵循四步法逻辑，强制校验导管前置条件。
    - 步骤1：铺设基础回路 (N, PE)
    - 步骤2：连接非受控单元 (L_电源)
    - 步骤3：计算控制线布局 (L_控制)
    - 步骤4：回灌电源火线 (L_电源)
5. **智能纠错与提示**：防止重复 ID、跨回路混穿导线、未建导管即计算等逻辑错误。

## 安装与运行

### 依赖安装
请确保已安装 Python 3.9+，并在项目根目录下运行：
```bash
pip install -r requirements.txt
```

### 运行程序
```bash
python main.py
```

## 使用指南
1. **绘制布局**：
    - 使用左侧工具栏选择节点类型，在画布上点击放置。
    - **技巧**：在属性面板设置好参数后点击“锁定”，可快速放置多个相同配置的节点。
2. **定义回路与单元**（流程建议）：
    - **回路管理**：若有多个配电箱，先使用“回路管理”划分区域（单配电箱场景可跳过，系统会自动补全）。
    - **单元管理**：定义受控按键与电器关系，或自动识别非受控插座。
3. **生成导管与布线**：
    - 点击“导管工具”生成物理连接（基于回路内节点的 MST 算法）。
    - 点击“生成布线方案”，系统将自动计算所有导线并更新标注。
4. **编辑与调试**：
    - **双击属性**：选中对象后，在右侧面板双击灰色背景区域即可修改参数。
    - **删除对象**：选中后按 `Delete` 键。
    - **恢复状态**：操作过程中随时按 `Esc` 回到选择模式。

## 注意事项
- 系统强制执行“回路 -> 单元 -> 导管 -> 布线”的逻辑顺序。
- 导管是布线的物理载体，未创建导管前无法执行布线计算。
- 非配电箱节点在逻辑上只能属于一个回路。
