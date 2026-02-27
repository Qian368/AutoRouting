from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QPushButton, QSpinBox, 
                             QDialogButtonBox, QListWidget, QAbstractItemView, QMessageBox)
from src.backend.models import NodeType, Node
from src.common import messages

# 节点属性对话框
class NodePropertyDialog(QDialog):
    def __init__(self, node_type: NodeType, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"添加 {node_type.value}")
        self.node_type = node_type
        self.layout = QVBoxLayout(self)
        
        # 标签
        self.layout.addWidget(QLabel(messages.PROP_LABEL))
        self.label_edit = QLineEdit()
        self.layout.addWidget(self.label_edit)
        
        # 特定属性
        self.gangs_spin = None
        self.power_spin = None
        
        if node_type == NodeType.SWITCH:
            self.layout.addWidget(QLabel(messages.PROP_SWITCH_GANGS))
            self.gangs_spin = QSpinBox()
            self.gangs_spin.setRange(1, 4)
            self.layout.addWidget(self.gangs_spin)
            
        elif node_type in (NodeType.LIGHT, NodeType.SOCKET):
            self.layout.addWidget(QLabel(messages.PROP_POWER))
            self.power_spin = QSpinBox()
            self.power_spin.setRange(0, 10000)
            self.power_spin.setValue(100 if node_type == NodeType.LIGHT else 2000)
            self.layout.addWidget(self.power_spin)
            
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout.addWidget(buttons)
        
    def get_data(self):
        data = {"label": self.label_edit.text()}
        if self.gangs_spin:
            data["gangs"] = self.gangs_spin.value()
        if self.power_spin:
            data["power"] = self.power_spin.value()
        return data

# 单元定义对话框
class UnitDefinitionDialog(QDialog):
    def __init__(self, switch_node: Node, gang_index: int, available_lights: list[Node], parent=None, initial_selection=None):
        super().__init__(parent)
        self.setWindowTitle(messages.DLG_UNIT_DEFINITION_TITLE)
        self.resize(400, 300)
        self.layout = QVBoxLayout(self)
        
        msg = messages.DLG_UNIT_DEFINITION_MSG.format(
            switch_label=switch_node.label,
            gang_index=gang_index
        )
        self.layout.addWidget(QLabel(msg))
        
        self.light_list = QListWidget()
        self.light_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        
        initial_selection = initial_selection or []
        
        for light in available_lights:
            self.light_list.addItem(f"{light.label}（{light.node_type.value}） (ID: {light.id})")
            # Store node ID in user role or just use index mapping if list doesn't change
            item = self.light_list.item(self.light_list.count() - 1)
            item.setData(100, light.id) # UserRole = 100
            
            if light.id in initial_selection:
                item.setSelected(True)
            
        self.layout.addWidget(self.light_list)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout.addWidget(buttons)
        
    def get_selected_light_ids(self):
        selected_ids = []
        for item in self.light_list.selectedItems():
            selected_ids.append(item.data(100))
        return selected_ids

# 开关与联数选择对话框
class SwitchGangSelectDialog(QDialog):
    def __init__(self, switches: list[Node], parent=None):
        super().__init__(parent)
        self.setWindowTitle(messages.DLG_SELECT_SWITCH_TITLE)
        self.resize(360, 160)
        self.layout = QVBoxLayout(self)
        self.switches = [s for s in switches if s.node_type == NodeType.SWITCH and (s.gangs or 0) > 0]
        if not self.switches:
            QMessageBox.warning(self, messages.DLG_WARNING_TITLE, messages.MSG_NO_SWITCHES)
            self.reject()
            return
        # 选择开关
        self.layout.addWidget(QLabel(messages.DLG_SELECT_SWITCH_LABEL))
        self.cmb_switch = QComboBox()
        for s in self.switches:
            self.cmb_switch.addItem(f"{s.label} (ID:{s.id})", s.id)
        self.layout.addWidget(self.cmb_switch)
        # 选择联数
        self.layout.addWidget(QLabel(messages.DLG_SELECT_GANG_LABEL))
        self.spin_gang = QSpinBox()
        self.spin_gang.setRange(1, self.switches[0].gangs or 1)
        self.layout.addWidget(self.spin_gang)
        # 联动：切换开关时更新联数范围
        def on_switch_changed():
            idx = self.cmb_switch.currentIndex()
            sw = self.switches[idx]
            self.spin_gang.setRange(1, sw.gangs or 1)
        self.cmb_switch.currentIndexChanged.connect(on_switch_changed)
        # 确认/取消
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout.addWidget(buttons)
    def get_selection(self):
        if not self.switches:
            return None, None
        idx = self.cmb_switch.currentIndex()
        sw = self.switches[idx]
        return sw, int(self.spin_gang.value())
