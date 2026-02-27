from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton, 
                             QComboBox, QMessageBox)
from PyQt6.QtCore import Qt
from src.backend.models import NodeType
from src.frontend.canvas import NodeItem, ConduitItem
from src.common import messages

class PropertyPanelManager:
    """属性面板管理器，负责更新和维护属性面板内容"""
    def __init__(self, main_window):
        self.main_window = main_window
        self.prop_layout = main_window.prop_layout
        self.system = main_window.system
        self.scene = main_window.scene

    def clear_prop_layout(self):
        """清空属性面板布局"""
        while self.prop_layout.count():
            child = self.prop_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                # 递归清理嵌套布局
                self._clear_layout(child.layout())

    def _clear_layout(self, layout):
        """递归清理布局及其子控件"""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def create_readonly_label(self, text, tooltip="双击编辑"):
        """创建只读标签，支持双击编辑"""
        label = QLabel(text)
        label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 2px; border: 1px solid #ccc; }")
        label.setToolTip(tooltip)
        return label

    def create_editable_field(self, initial_value, field_type="line", **kwargs):
        """创建可编辑字段，支持双击切换编辑状态"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建只读标签
        if field_type == "line":
            display = self.create_readonly_label(str(initial_value))
            editor = QLineEdit(str(initial_value))
        elif field_type == "spin":
            display = self.create_readonly_label(str(initial_value))
            editor = QSpinBox()
            editor.setRange(kwargs.get("min", 0), kwargs.get("max", 100))
            editor.setValue(initial_value)
        elif field_type == "double_spin":
            display = self.create_readonly_label(f"{initial_value:.2f}")
            editor = QDoubleSpinBox()
            editor.setRange(kwargs.get("min", 0.0), kwargs.get("max", 100.0))
            editor.setDecimals(kwargs.get("decimals", 2))
            editor.setSingleStep(kwargs.get("step", 0.1))
            editor.setValue(initial_value)
        
        editor.setVisible(False)
        layout.addWidget(display)
        layout.addWidget(editor)
        
        def start_edit():
            display.setVisible(False)
            editor.setVisible(True)
            editor.setFocus()
            if hasattr(editor, "selectAll"):
                editor.selectAll()
        
        def finish_edit():
            editor.setVisible(False)
            display.setVisible(True)
            if field_type == "line":
                display.setText(editor.text())
            elif field_type == "spin":
                display.setText(str(editor.value()))
            elif field_type == "double_spin":
                display.setText(f"{editor.value():.2f}")
        
        display.mouseDoubleClickEvent = lambda e: start_edit()
        editor.editingFinished.connect(finish_edit)
        
        container.editor = editor
        container.display = display
        container.get_value = lambda: editor.text() if field_type == "line" else editor.value()
        
        return container

    def update_panel(self):
        """更新属性面板内容"""
        self.clear_prop_layout()
        selected = self.scene.selectedItems()
        
        if not selected:
            # 未选中任何项时，如果处于添加模式，展示默认参数编辑
            if self.scene.mode == "add_node" and self.scene.current_node_type:
                d = self.main_window.add_defaults.get(self.scene.current_node_type, {})
                
                # 添加标题和锁定按钮
                title_container = QWidget()
                title_layout = QHBoxLayout(title_container)
                title_layout.setContentsMargins(0, 0, 0, 0)
                title_layout.addWidget(QLabel(messages.PROP_DEFAULTS_TITLE))
                
                lock_btn = QPushButton(messages.PROP_LOCK_DEFAULTS if not self.main_window.defaults_locked else messages.PROP_UNLOCK_DEFAULTS)
                lock_btn.clicked.connect(self.main_window.toggle_defaults_lock)
                title_layout.addWidget(lock_btn)
                title_layout.addStretch()
                
                self.prop_layout.addRow(title_container)
                
                # 如果参数已锁定，显示锁定状态但不允许编辑
                if self.main_window.defaults_locked:
                    self.prop_layout.addRow(QLabel(messages.PROP_DEFAULT_LABEL), QLabel(d.get("label_prefix", "")))
                    self.prop_layout.addRow(QLabel(messages.PROP_DEFAULT_ID), QLabel(d.get("id", "") or "自动生成"))
                    if self.scene.current_node_type == NodeType.SWITCH:
                        self.prop_layout.addRow(QLabel(messages.PROP_DEFAULT_GANGS), QLabel(str(d.get("gangs", 1))))
                    if self.scene.current_node_type in (NodeType.LIGHT, NodeType.SOCKET):
                        self.prop_layout.addRow(QLabel(messages.PROP_DEFAULT_POWER), QLabel(str(d.get("power", 0))))
                    self.prop_layout.addRow(QLabel(messages.PROP_DEFAULT_RATED_CURRENT), QLabel(f"{d.get('rated_current', 0.0):.2f}"))
                else:
                    # 正常编辑模式
                    id_default = QLineEdit(d.get("id", ""))
                    id_default.editingFinished.connect(lambda: d.__setitem__("id", id_default.text().strip()))
                    self.prop_layout.addRow(QLabel(messages.PROP_DEFAULT_ID), id_default)
                    
                    label_prefix = QLineEdit(d.get("label_prefix", ""))
                    label_prefix.editingFinished.connect(lambda: d.__setitem__("label_prefix", label_prefix.text()))
                    self.prop_layout.addRow(QLabel(messages.PROP_DEFAULT_LABEL), label_prefix)
                    
                    if self.scene.current_node_type == NodeType.SWITCH:
                        gangs_default = QSpinBox()
                        gangs_default.setRange(1, 8)
                        gangs_default.setValue(int(d.get("gangs", 1)))
                        gangs_default.valueChanged.connect(lambda v: d.__setitem__("gangs", int(v)))
                        self.prop_layout.addRow(QLabel(messages.PROP_DEFAULT_GANGS), gangs_default)
                    
                    if self.scene.current_node_type in (NodeType.LIGHT, NodeType.SOCKET):
                        power_default = QSpinBox()
                        power_default.setRange(0, 10000)
                        power_default.setValue(int(d.get("power", 0)))
                        power_default.valueChanged.connect(lambda v: d.__setitem__("power", int(v)))
                        self.prop_layout.addRow(QLabel(messages.PROP_DEFAULT_POWER), power_default)
                    
                    rc_default = QDoubleSpinBox()
                    rc_default.setRange(0.0, 100.0)
                    rc_default.setDecimals(2)
                    rc_default.setSingleStep(0.1)
                    rc_default.setValue(float(d.get("rated_current", 0.0)))
                    rc_default.valueChanged.connect(lambda v: d.__setitem__("rated_current", float(v)))
                    self.prop_layout.addRow(QLabel(messages.PROP_DEFAULT_RATED_CURRENT), rc_default)
            return

        # 只要选中了项，就处理第一个
        item = selected[0]
        # 递归寻找父项直到 NodeItem 或 ConduitItem
        while item and not isinstance(item, (NodeItem, ConduitItem)):
            item = item.parentItem()
            
        if isinstance(item, NodeItem):
            self._update_node_properties(item.node)
        elif isinstance(item, ConduitItem):
            self._update_conduit_properties(item.conduit)

    def _update_node_properties(self, node):
        """更新节点属性显示"""
        # 编辑ID（双击编辑）
        id_field = self.create_editable_field(node.id, "line")
        def on_id_changed():
            new_id = id_field.get_value().strip()
            if not new_id:
                QMessageBox.warning(self.main_window, messages.DLG_WARNING_TITLE, messages.MSG_ID_EMPTY)
                id_field.editor.setText(node.id)
                id_field.display.setText(node.id)
                return
            try:
                self.system.rename_node_id(node.id, new_id)
                self.main_window.refresh_scene_full()
            except Exception as e:
                QMessageBox.warning(self.main_window, messages.DLG_WARNING_TITLE, str(e))
                id_field.editor.setText(node.id)
                id_field.display.setText(node.id)
        id_field.editor.editingFinished.connect(on_id_changed)
        self.prop_layout.addRow(QLabel(messages.PROP_EDIT_ID + f" ({messages.PROP_DOUBLE_CLICK_TO_EDIT})"), id_field)
        
        # 编辑标签（双击编辑）
        label_field = self.create_editable_field(node.label, "line")
        label_field.editor.editingFinished.connect(
            lambda: setattr(node, "label", label_field.get_value())
        )
        self.prop_layout.addRow(QLabel(messages.PROP_EDIT_LABEL + f" ({messages.PROP_DOUBLE_CLICK_TO_EDIT})"), label_field)
        
        # 类型特定（双击编辑）
        if node.node_type == NodeType.SWITCH:
            gangs_field = self.create_editable_field(int(node.gangs or 1), "spin", min=1, max=8)
            gangs_field.editor.valueChanged.connect(lambda v: setattr(node, "gangs", int(v)))
            self.prop_layout.addRow(QLabel(messages.PROP_EDIT_GANGS + f" ({messages.PROP_DOUBLE_CLICK_TO_EDIT})"), gangs_field)
        
        if node.node_type in (NodeType.LIGHT, NodeType.SOCKET):
            power_field = self.create_editable_field(int(node.power or 0), "spin", min=0, max=10000)
            power_field.editor.valueChanged.connect(lambda v: setattr(node, "power", int(v)))
            self.prop_layout.addRow(QLabel(messages.PROP_EDIT_POWER + f" ({messages.PROP_DOUBLE_CLICK_TO_EDIT})"), power_field)
        
        # 额定电流与用途（双击编辑）
        rc_field = self.create_editable_field(float(node.rated_current or 0.0), "double_spin", min=0.0, max=100.0, decimals=2, step=0.1)
        rc_field.editor.valueChanged.connect(lambda v: setattr(node, "rated_current", float(v)))
        self.prop_layout.addRow(QLabel(messages.PROP_EDIT_RATED_CURRENT + f" ({messages.PROP_DOUBLE_CLICK_TO_EDIT})"), rc_field)
        
        usage_field = self.create_editable_field(node.usage or "", "line")
        usage_field.editor.editingFinished.connect(lambda: setattr(node, "usage", usage_field.get_value()))
        self.prop_layout.addRow(QLabel(messages.PROP_EDIT_USAGE + f" ({messages.PROP_DOUBLE_CLICK_TO_EDIT})"), usage_field)
        
        # 所属单元编辑（仅限用电节点：灯具、插座、接线盒）
        if node.node_type in (NodeType.LIGHT, NodeType.SOCKET, NodeType.JUNCTION_BOX):
            unit_combo = QComboBox()
            unit_combo.addItem("无", None)
            
            # 获取所有已定义的单元，按受控/非受控分类
            units = sorted(self.system.units.values(), key=lambda u: u.id)
            current_unit_id = node.controlled_unit_id or node.uncontrolled_unit_id
            
            for unit in units:
                unit_combo.addItem(f"{unit.name} ({unit.id})", unit.id)
                if unit.id == current_unit_id:
                    unit_combo.setCurrentIndex(unit_combo.count() - 1)
            
            def on_unit_changed(index):
                new_unit_id = unit_combo.currentData()
                # 清除旧关系
                if node.controlled_unit_id:
                    old_unit = self.system.units.get(node.controlled_unit_id)
                    if old_unit and node.id in old_unit.member_node_ids:
                        old_unit.member_node_ids.remove(node.id)
                if node.uncontrolled_unit_id:
                    old_unit = self.system.units.get(node.uncontrolled_unit_id)
                    if old_unit and node.id in old_unit.member_node_ids:
                        old_unit.member_node_ids.remove(node.id)
                
                node.controlled_unit_id = None
                node.uncontrolled_unit_id = None
                
                # 建立新关系
                if new_unit_id:
                    new_unit = self.system.units.get(new_unit_id)
                    if new_unit:
                        if new_unit.unit_type == "受控":
                            node.controlled_unit_id = new_unit_id
                        else:
                            node.uncontrolled_unit_id = new_unit_id
                        if node.id not in new_unit.member_node_ids:
                            new_unit.member_node_ids.append(node.id)
                
                self.main_window.status_bar.showMessage(f"节点 {node.id} 单元已更新")
            
            unit_combo.currentIndexChanged.connect(on_unit_changed)
            self.prop_layout.addRow(QLabel("所属单元"), unit_combo)

        # 非编辑信息
        self.prop_layout.addRow(QLabel(messages.PROP_TYPE), QLabel(node.node_type.value))
        self.prop_layout.addRow(QLabel(messages.PROP_POSITION), QLabel(f"({int(node.x)}, {int(node.y)})"))

    def _update_conduit_properties(self, conduit):
        """更新导管属性显示"""
        start = self.system.nodes.get(conduit.start_node_id)
        end = self.system.nodes.get(conduit.end_node_id)
        
        # 展示导管基本信息
        self.prop_layout.addRow(QLabel(messages.PROP_ID), QLabel(conduit.id))
        self.prop_layout.addRow(QLabel(messages.PROP_START_NODE), QLabel(start.label if start else conduit.start_node_id))
        self.prop_layout.addRow(QLabel(messages.PROP_END_NODE), QLabel(end.label if end else conduit.end_node_id))
        self.prop_layout.addRow(QLabel(messages.PROP_LENGTH), QLabel(f"{conduit.length:.1f}"))
        
        if conduit.circuit_id:
            self.prop_layout.addRow(QLabel("所属回路"), QLabel(conduit.circuit_id))
        
        # 导线统计
        if conduit.wires:
            self.prop_layout.addRow(QLabel("-" * 20), QLabel("-" * 20))
            self.prop_layout.addRow(QLabel("【导线详情】"), QLabel(f"共 {len(conduit.wires)} 根"))
            
            counts = {}
            sum_current = 0.0
            for i, w in enumerate(conduit.wires):
                sum_current += getattr(w, "current", 0.0)
                counts[w.wire_type] = counts.get(w.wire_type, 0) + 1
                
                # 每一根导线的详细属性
                wire_info = f"{w.wire_type.value}"
                if w.unit_id:
                    wire_info += f" (单元:{w.unit_id})"
                if w.current > 0:
                    wire_info += f" 电流:{w.current:.2f}A"
                
                self.prop_layout.addRow(QLabel(f"导线 {i+1}"), QLabel(wire_info))
            
            self.prop_layout.addRow(QLabel("-" * 20), QLabel("-" * 20))
            # 统计摘要
            summary = "； ".join([f"{wt.value}:{counts[wt]}根" for wt in counts])
            self.prop_layout.addRow(QLabel(messages.PROP_WIRES), QLabel(summary))
            self.prop_layout.addRow(QLabel(messages.PROP_WIRE_SUM_CURRENT), QLabel(f"{sum_current:.2f} A"))
        else:
            self.prop_layout.addRow(QLabel(messages.PROP_WIRES), QLabel("无导线"))
