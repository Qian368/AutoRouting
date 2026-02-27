
import sys
import uuid
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QToolBar, QGraphicsView, QLabel, QStatusBar,
                             QMessageBox, QDockWidget, QFormLayout, QDialog,
                             QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton,
                             QComboBox)
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtCore import Qt

from src.backend.models import CircuitSystem, Node, Conduit, Unit, NodeType
from src.backend.algorithms import WiringCalculator, TopologyGenerator
from src.frontend.canvas import CircuitScene, NodeItem, ConduitItem
from src.frontend.dialogs import NodePropertyDialog, UnitDefinitionDialog, SwitchGangSelectDialog
from src.frontend.unit_manager import UnitManagerDialog
from src.frontend.circuit_manager import CircuitManagerDialog
from src.frontend.property_panel import PropertyPanelManager
from src.common import messages

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(messages.APP_TITLE)
        self.resize(messages.APP_WIDTH, messages.APP_HEIGHT)
        
        # 数据模型
        self.system = CircuitSystem()
        
        # UI 组件
        self.setup_ui()

        # 属性面板管理器
        self.prop_manager = PropertyPanelManager(self)
        self.scene.selectionChanged.connect(self.prop_manager.update_panel)   # 场景选择改变后更新属性面板

        # 状态变量
        self.current_action = None  # 当前选中的工具动作
        self.node_counter = 0   # 节点计数器
        self.conduit_counter = 0   # 导管计数器
        self.unit_counter = 0   # 单元计数器
        self.id_counters = {"DB": 0, "SW": 0, "LT": 0, "SK": 0, "JB": 0, "C-UT": 0, "U-UT": 0,"CT": 0}     # 节点ID前缀计数器，补充包含受控单元、非受控单元、回路类型
        # 新增节点默认参数（按工具类型）
        self.add_defaults = {
            NodeType.DISTRIBUTION_BOX: {"id": "", "label_prefix": messages.TOOL_DISTRIBUTION_BOX, "rated_current": 0.0},
            NodeType.SWITCH: {"id": "", "label_prefix": messages.TOOL_SWITCH, "rated_current": 0.0, "gangs": 1},
            NodeType.LIGHT: {"id": "", "label_prefix": messages.TOOL_LIGHT, "rated_current": 0.0, "power": 100},
            NodeType.SOCKET: {"id": "", "label_prefix": messages.TOOL_SOCKET, "rated_current": 0.0, "power": 2000},
            NodeType.JUNCTION_BOX: {"id": "", "label_prefix": messages.TOOL_JUNCTION_BOX, "rated_current": 0.0},
        }
        # 默认参数锁定状态
        self.defaults_locked = False
        
        # 鼠标默认为选择工具
        self.enable_box_selection()
        
    def setup_ui(self):
        # 1. 画布
        self.scene = CircuitScene(0, 0, 2000, 2000)
        self.view = QGraphicsView(self.scene)   # 画布视图
        self.view.setRenderHint(self.view.renderHints().Antialiasing)   # 开启抗锯齿渲染
        self.setCentralWidget(self.view)    # 设置画布视图为中心窗口
        
        # 连接画布信号
        self.scene.node_create_requested.connect(self.add_node_at)   # 节点创建请求信号连接到添加节点方法
        self.scene.conduit_requested.connect(self.create_conduit)   # 导管请求信号连接到创建导管方法
        
        # 2. 工具栏
        self.toolbar = QToolBar("Tools")
        self.addToolBar(self.toolbar)   # 工具栏添加到主窗口
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.toolbar)        # 工具栏贴靠左侧
        
        # self.add_tool_action(messages.TOOL_SELECT, self.set_select_mode) # 选择工具
        self.add_tool_action(messages.TOOL_SELECT, self.enable_box_selection)   # 框选工具  暂未实现

        self.toolbar.addSeparator() # 分隔符
        self.add_tool_action(messages.TOOL_DISTRIBUTION_BOX, lambda: self.set_add_node_mode(NodeType.DISTRIBUTION_BOX))
        self.add_tool_action(messages.TOOL_SWITCH, lambda: self.set_add_node_mode(NodeType.SWITCH))
        self.add_tool_action(messages.TOOL_LIGHT, lambda: self.set_add_node_mode(NodeType.LIGHT))
        self.add_tool_action(messages.TOOL_SOCKET, lambda: self.set_add_node_mode(NodeType.SOCKET))
        self.add_tool_action(messages.TOOL_JUNCTION_BOX, lambda: self.set_add_node_mode(NodeType.JUNCTION_BOX))

        self.toolbar.addSeparator() # 分隔符
        self.add_tool_action(messages.TOOL_CIRCUIT_MANAGER, self.manage_circuits)  # 回路管理器     

        self.toolbar.addSeparator() # 分隔符  
        self.add_tool_action(messages.BTN_DEFINE_UNITS, self.manage_units)  # 定义单元
        self.add_tool_action(messages.BTN_DEFINE_CONTROLLED_FROM_SELECTION, self.define_controlled_from_selection)  # 从选择定义受控元件
        self.add_tool_action(messages.BTN_DEFINE_UNCONTROLLED_FROM_SELECTION, self.define_uncontrolled_from_selection)  # 从选择定义非受控元件
       
        self.toolbar.addSeparator() # 分隔符
        self.add_tool_action(messages.TOOL_CONDUIT, self.auto_connect_conduits)   # 导管工具
        self.add_tool_action(messages.BTN_CALCULATE_WIRING, self.calculate_wiring) # 计算布线
        
        self.toolbar.addSeparator() # 分隔符
        
        # 3. 菜单栏
        menu_bar = self.menuBar()
        
        # 文件菜单
        file_menu = menu_bar.addMenu(messages.MENU_FILE)
        file_menu.addAction(messages.MENU_FILE_EXIT, self.close)
        
        # 调试菜单  
        debug_menu = menu_bar.addMenu(messages.MENU_DEBUG)
        
        action_clear_nodes = QAction(messages.MENU_DEBUG_CLEAR_NODES, self)
        action_clear_nodes.triggered.connect(self.clear_all_nodes)
        debug_menu.addAction(action_clear_nodes)
        
        action_clear_conduits = QAction(messages.MENU_DEBUG_CLEAR_CONDUITS, self)
        action_clear_conduits.triggered.connect(self.clear_all_conduits)
        debug_menu.addAction(action_clear_conduits)
        
        action_clear_wires = QAction(messages.MENU_DEBUG_CLEAR_WIRES, self)
        action_clear_wires.triggered.connect(self.clear_all_wires)
        debug_menu.addAction(action_clear_wires)
        
        debug_menu.addSeparator()
        
        action_delete_selected = QAction(messages.MENU_DEBUG_DELETE_SELECTED, self)
        action_delete_selected.triggered.connect(self.delete_selected_items)
        action_delete_selected.setShortcut(QKeySequence.StandardKey.Delete)
        debug_menu.addAction(action_delete_selected)
        
        # 4. 状态栏
        self.status_bar = QStatusBar()  # 状态栏
        self.setStatusBar(self.status_bar)  # 设置状态栏
        self.status_bar.showMessage("Ready")    # 状态栏显示Ready消息
        
        # 5.属性面板展示盒
        self.prop_dock = QDockWidget(messages.PROP_PANEL_TITLE, self)   # 属性面板展示盒
        self.prop_widget = QWidget()    # 属性面板展示盒的内容区域
        self.prop_dock.setWidget(self.prop_widget)  # 属性面板展示盒的内容区域设置为属性面板展示盒的内容区域        
        self.prop_layout = QFormLayout(self.prop_widget)    # 属性面板展示盒的内容区域布局为表单布局
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.prop_dock)   # 属性面板展示盒添加到主窗口
        file_menu.addAction(messages.MENU_FILE_OPEN_PROP_PANEL, self.prop_dock.show)       # 属性面板打开关闭按钮

    def keyPressEvent(self, event):
        """处理键盘事件：按下ESC键切换回框选模式"""
        if event.key() == Qt.Key.Key_Escape:
            self.enable_box_selection()
        else:
            super().keyPressEvent(event)

    def add_tool_action(self, name, callback):
        action = QAction(name, self)
        action.triggered.connect(callback)
        self.toolbar.addAction(action)

    def enable_box_selection(self):
        self.scene.mode = "select"
        self.scene.reset_temp_state()
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.status_bar.showMessage(messages.MSG_SELECT_MODE)

    def set_add_node_mode(self, node_type: NodeType):
        self.scene.mode = "add_node"
        self.scene.current_node_type = node_type
        self.status_bar.showMessage(messages.MSG_ADD_NODE_MODE.format(node_type=node_type.value))   # 状态栏显示添加节点工具提示        
        self.prop_manager.update_panel()       # 确保属性面板显示默认参数区域

    def _prefix_for(self, node_type: NodeType) -> str:  # 节点类型映射
        if node_type == NodeType.DISTRIBUTION_BOX:
            return "DB"
        if node_type == NodeType.SWITCH:
            return "SW"
        if node_type == NodeType.LIGHT:
            return "LT"
        if node_type == NodeType.SOCKET:
            return "SK"
        if node_type == NodeType.JUNCTION_BOX:
            return "JB"
        return "ND"
    
    def add_node_at(self, x, y):    
        """
        在场景中添加一个新节点，节点类型为当前选择的类型。
        节点ID优先使用属性面板设置的默认ID；为空则按类型前缀+最小缺失序号生成。
        其他默认参数（标签前缀、额定电流、功率、开关联数）亦从属性面板读取。
        """
        prefix = self._prefix_for(self.scene.current_node_type)
        d = self.add_defaults.get(self.scene.current_node_type, {})
        manual_id = (d.get("id") or "").strip()
        if manual_id:
            if manual_id in self.system.nodes:
                QMessageBox.warning(self, messages.DLG_WARNING_TITLE, messages.MSG_ID_EXISTS)
                return
            node_id = manual_id
        else:
            max_seq = max(
                (int(node_id[len(prefix):]) for node_id in self.system.nodes if node_id.startswith(prefix)),
                default=0
            )
            existing_seqs = {int(node_id[len(prefix):]) for node_id in self.system.nodes if node_id.startswith(prefix)}
            all_seqs = set(range(1, max_seq + 2))
            missing_seqs = all_seqs - existing_seqs
            seq = min(missing_seqs, default=max_seq + 1)
            node_id = f"{prefix}{seq}"
        label_prefix = d.get("label_prefix") or self.scene.current_node_type.value
        # 如果按前缀生成ID，则标签使用序号；若使用手动ID，不强制带序号
        label = f"{label_prefix}{node_id[len(prefix):]}" if node_id.startswith(prefix) else f"{label_prefix}"
        
        node = Node(
            id=node_id,
            node_type=self.scene.current_node_type,
            x=x,
            y=y,
            label=label
        )
        
        # 默认属性
        if node.node_type == NodeType.SWITCH:
            node.gangs = int(d.get("gangs", 1))
        if node.node_type in (NodeType.LIGHT, NodeType.SOCKET):
            node.power = int(d.get("power", node.power or 0))
        node.rated_current = float(d.get("rated_current", node.rated_current or 0.0))
        # 使用后清空手动ID，避免重复（仅在参数未锁定时）
        if manual_id and not self.defaults_locked:
            d["id"] = ""
            
        self.system.add_node(node)
        self.scene.add_node_item(node)
        self.status_bar.showMessage(f"Added node: {label}")
        
        # 恢复选择模式? 或者保持添加模式? 保持添加模式方便连续添加
        # self.set_select_mode()

    def create_conduit(self, start_id, end_id):
        # 检查是否已存在
        if self.system.get_conduit(start_id, end_id):
            self.status_bar.showMessage("Conduit already exists")
            return

        # 生成更易读的导管ID
        existing_manual = [cid for cid in self.system.conduits.keys() if cid.startswith("c_manual_")]
        seq = len(existing_manual) + 1
        conduit_id = f"c_manual_{seq}"
        
        conduit = Conduit(id=conduit_id, start_node_id=start_id, end_node_id=end_id)
        self.system.add_conduit(conduit)
        self.scene.add_conduit_item(conduit)
        self.status_bar.showMessage("Conduit connected")

    def auto_connect_conduits(self):
        """自动生成MST导管连接"""
        if not self.system.circuits:
            QMessageBox.warning(self, messages.DLG_WARNING_TITLE, messages.MSG_NO_CIRCUITS)
            return
        count = TopologyGenerator.generate_mst_topology(self.system)
        if count <= 0:
            QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_NO_NEW_CONDUITS)
            return

        # 刷新视图
        self.refresh_scene_full()
        self.status_bar.showMessage(messages.MSG_AUTO_CONDUITS_DONE_PER_CIRCUIT.format(count=count))

    def manage_units(self):
        """打开单元管理对话框"""
        dlg = UnitManagerDialog(self.system, self, mode="manager")
        dlg.exec()
    
    def manage_circuits(self):
        """打开回路管理器"""
        dlg = CircuitManagerDialog(self.system, self)
        dlg.exec()
    
    def _selected_device_nodes(self):
        ids = []
        for item in self.scene.selectedItems():
            if isinstance(item, NodeItem):
                if item.node.node_type in (NodeType.LIGHT, NodeType.SOCKET):
                    ids.append(item.node.id)
        return ids
    
    def define_uncontrolled_from_selection(self):
        """基于当前选择定义非受控单元"""
        selected_ids = self._selected_device_nodes()
        if not selected_ids:
            QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_NO_SELECTION)
            return
        # 过滤掉已属于单元的节点
        final_ids = []
        for nid in selected_ids:
            n = self.system.nodes.get(nid)
            if n and (n.controlled_unit_id is None and n.uncontrolled_unit_id is None):
                final_ids.append(nid)
        if not final_ids:
            QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_NO_MORE_DEVICES)
            return
        # 创建单元（顺序ID：U-UTx）
        unit_id = self.system.generate_unit_id("非受控")
        name = self.system.generate_unit_name("非受控")
        unit = Unit(id=unit_id, name=name, unit_type="非受控", description="基于选择创建", member_node_ids=final_ids)
        self.system.add_unit(unit)
        for nid in final_ids:
            node = self.system.nodes.get(nid)
            if node:
                node.uncontrolled_unit_id = unit_id
        QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_CREATED_UNCONTROLLED.format(unit_name=name, count=len(final_ids)))
        self.prop_manager.update_panel()
    
    def define_controlled_from_selection(self):
        """基于当前选择定义受控单元（需选择开关与联数）"""
        selected_ids = self._selected_device_nodes()
        if not selected_ids:
            QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_NO_SELECTION)
            return
        switches = [n for n in self.system.nodes.values() if n.node_type == NodeType.SWITCH and (n.gangs or 0) > 0]
        if not switches:
            QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_NO_SWITCHES)
            return
        dlg = SwitchGangSelectDialog(switches, self)
        if dlg.exec():
            switch, gang = dlg.get_selection()
            if not switch:
                return
            # 过滤已分配
            candidates = []
            for nid in selected_ids:
                n = self.system.nodes.get(nid)
                if n and (n.controlled_unit_id is None and n.uncontrolled_unit_id is None):
                    candidates.append(n)
            if not candidates:
                QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_NO_MORE_DEVICES)
                return
            # 打开成员选择对话框，预选当前选择
            udlg = UnitDefinitionDialog(switch, gang, candidates, self, initial_selection=[n.id for n in candidates])
            if udlg.exec():
                final_ids = udlg.get_selected_light_ids()
                if not final_ids:
                    return
                # 创建受控单元（顺序ID：C-UTx）
                unit_id = self.system.generate_unit_id("受控")
                unit_name = f"{switch.label}_按键{gang}"
                unit = Unit(
                    id=unit_id, name=unit_name, unit_type="受控",
                    description=f"由 {switch.label} 第{gang}联控制",
                    member_node_ids=final_ids, control_switch_id=switch.id, switch_gang_index=gang
                )
                self.system.add_unit(unit)
                for nid in final_ids:
                    node = self.system.nodes.get(nid)
                    if node:
                        node.controlled_unit_id = unit_id
                QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_CREATED_CONTROLLED.format(
                    unit_name=unit_name, count=len(final_ids), switch_label=switch.label, gang=gang
                ))
                self.prop_manager.update_panel()

    def calculate_wiring(self):
        """执行四步法布线计算"""
        if not self.system.conduits:
            QMessageBox.warning(self, messages.DLG_WARNING_TITLE, messages.MSG_NO_CONDUITS)
            return
        dlg = UnitManagerDialog(self.system, self, mode="confirmation")
        # 确认单元定义
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        # 执行布线计算
        try:
            calculator = WiringCalculator(self.system)
            calculator.calculate()
            self.scene.update_all_conduits_visuals()
            QMessageBox.information(self, messages.DLG_CALC_SUCCESS, messages.DLG_CALC_SUCCESS_MSG)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, messages.DLG_ERROR_TITLE, str(e))

    # ---------- 调试功能 ----------
    
    def refresh_scene_full(self):
        """全量刷新场景"""
        self.scene.clear()
        self.scene.node_items.clear()
        self.scene.conduit_items.clear()
        
        # 重新添加节点
        for node in self.system.nodes.values():
            self.scene.add_node_item(node)
            
        # 重新添加导管
        for conduit in self.system.conduits.values():
            self.scene.add_conduit_item(conduit)

    def clear_all_nodes(self):
        """ 清空所有节点（确认后）"""
        reply = QMessageBox.question(self, messages.DLG_CONFIRM_TITLE, messages.DLG_CONFIRM_CLEAR_NODES,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.system.clear_nodes()
            self.refresh_scene_full()
            self.node_counter = 0
            self.id_counters = {"DB": 0, "SW": 0, "LT": 0, "SK": 0, "JB": 0}
            self.status_bar.showMessage("已清空所有节点")

    def clear_all_conduits(self):
        """ 清空所有导管（确认后）"""
        reply = QMessageBox.question(self, messages.DLG_CONFIRM_TITLE, messages.DLG_CONFIRM_CLEAR_CONDUITS,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.system.clear_conduits()
            self.refresh_scene_full()
            self.status_bar.showMessage("已清空所有导管")

    def clear_all_wires(self):
        """ 清空所有导线（确认后）"""
        reply = QMessageBox.question(self, messages.DLG_CONFIRM_TITLE, messages.DLG_CONFIRM_CLEAR_WIRES,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.system.clear_wires()
            self.scene.update_all_conduits_visuals()
            self.status_bar.showMessage("已清空所有导线")

    def delete_selected_items(self):
        """ 删除选中的项（确认后）"""
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return
            
        count = 0
        
        # 分类
        nodes_to_delete = []
        conduits_to_delete = []
        
        for item in selected_items:
            if isinstance(item, NodeItem):
                nodes_to_delete.append(item)
            elif isinstance(item, ConduitItem):
                conduits_to_delete.append(item)
        
        # 先删导管
        for item in conduits_to_delete:
            self.system.remove_conduit(item.conduit.id)
            count += 1
            
        # 再删节点 (会级联删除相连导管，但如果导管已经被删了也没关系，backend handle it)
        for item in nodes_to_delete:
            self.system.remove_node(item.node.id)
            count += 1
            
        # 刷新
        self.refresh_scene_full()
        self.status_bar.showMessage(messages.MSG_DELETED_ITEMS.format(count=count))
        self.prop_manager.update_panel()

    def toggle_defaults_lock(self):
        """切换默认参数锁定状态"""
        self.defaults_locked = not self.defaults_locked
        self.status_bar.showMessage(
            messages.MSG_PARAMS_LOCKED if self.defaults_locked else messages.MSG_PARAMS_UNLOCKED
        )
        self.prop_manager.update_panel()
    

