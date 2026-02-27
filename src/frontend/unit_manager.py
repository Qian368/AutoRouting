
import uuid
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QAbstractItemView, 
                             QMessageBox, QListWidgetItem, QWidget)
from PyQt6.QtCore import Qt
from src.backend.models import Unit, CircuitSystem, NodeType
from src.frontend.dialogs import UnitDefinitionDialog
from src.common import messages

# 受控单元管理器对话框
class UnitManagerDialog(QDialog):
    def __init__(self, system: CircuitSystem, parent=None, mode="manager"):
        super().__init__(parent)
        self.setWindowTitle(messages.DLG_UNIT_MANAGER_TITLE if mode == "manager" else messages.DLG_UNIT_CONFIRM_TITLE)
        self.resize(600, 500)
        self.system = system
        self.mode = mode
        self.system.ensure_default_single_circuit()
        
        self.layout = QVBoxLayout(self)
        
        # 说明文本
        if self.mode == "confirmation":
            self.lbl_info = QLabel(messages.MSG_UNIT_CONFIRM_INFO)
            self.lbl_info.setWordWrap(True)
            self.layout.addWidget(self.lbl_info)
        
        # 列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.layout.addWidget(self.list_widget)
        
        # 功能按钮栏
        action_layout = QHBoxLayout()
        
        self.btn_auto = QPushButton(messages.BTN_AUTO_DEFINE_UNCONTROLLED)
        self.btn_auto.setToolTip(messages.TIP_AUTO_DEFINE_UNCONTROLLED)
        self.btn_auto.clicked.connect(self.auto_define_uncontrolled)
        action_layout.addWidget(self.btn_auto)
        
        self.btn_add = QPushButton(messages.BTN_DEFINE_CONTROLLED)
        self.btn_add.setToolTip(messages.TIP_DEFINE_CONTROLLED)
        self.btn_add.clicked.connect(self.define_controlled)
        action_layout.addWidget(self.btn_add)
        
        self.btn_edit = QPushButton(messages.BTN_EDIT_UNIT)
        self.btn_edit.setToolTip(messages.TIP_EDIT_UNIT)
        self.btn_edit.clicked.connect(self.edit_unit)
        action_layout.addWidget(self.btn_edit)
        
        self.btn_delete = QPushButton(messages.BTN_DELETE_UNIT)
        self.btn_delete.clicked.connect(self.delete_unit)
        action_layout.addWidget(self.btn_delete)
        
        self.layout.addLayout(action_layout)
        
        # 底部按钮栏
        bottom_layout = QHBoxLayout()
        
        if self.mode == "confirmation":
            self.btn_confirm = QPushButton(messages.BTN_CONFIRM_GENERATE)
            self.btn_confirm.clicked.connect(self.accept)
            bottom_layout.addWidget(self.btn_confirm)
            
            self.btn_cancel = QPushButton(messages.BTN_CANCEL)
            self.btn_cancel.clicked.connect(self.reject)
            bottom_layout.addWidget(self.btn_cancel)
        else:
            self.btn_close = QPushButton(messages.BTN_CLOSE)
            self.btn_close.clicked.connect(self.accept)
            bottom_layout.addWidget(self.btn_close)
        
        self.layout.addLayout(bottom_layout)
        
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        # 按类型排序：先显示受控，再显示非受控
        sorted_units = sorted(self.system.units.values(), key=lambda u: (u.unit_type, u.name))
        
        for unit in sorted_units:
            item_text = f"[{unit.unit_type}] {unit.name}"
            if unit.description:
                item_text += f" - {unit.description}"
            
            # 显示成员数量
            item_text += f" (包含 {len(unit.member_node_ids)} 个节点)"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, unit.id)
            self.list_widget.addItem(item)

    def delete_unit(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            return
            
        unit_id = current_item.data(Qt.ItemDataRole.UserRole)
        unit = self.system.units.get(unit_id)
        
        if not unit:
            return
            
        confirm = QMessageBox.question(
            self, 
            messages.DLG_CONFIRM_TITLE,
            messages.DLG_CONFIRM_DELETE_UNIT.format(unit_name=unit.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            # 清除关联信息
            for node_id in unit.member_node_ids:
                node = self.system.nodes.get(node_id)
                if node:
                    if unit.unit_type == "受控":
                        node.controlled_unit_id = None
                    elif unit.unit_type == "非受控":
                        node.uncontrolled_unit_id = None
            
            del self.system.units[unit_id]
            self.refresh_list()

    def auto_define_uncontrolled(self):
        """自动识别非受控单元 (插座 -> 配电箱)"""
        # 1. 查找所有插座
        sockets = [n for n in self.system.nodes.values() if n.node_type == NodeType.SOCKET and n.controlled_unit_id is None]
        if not sockets:
            QMessageBox.information(self, messages.DLG_INFO_TITLE if hasattr(messages, 'DLG_INFO_TITLE') else messages.DLG_WARNING_TITLE, messages.MSG_NO_SOCKETS_INFO)
            return

        # 2. 检查是否有插座已经被分配
        assigned_sockets = [s for s in sockets if s.uncontrolled_unit_id]
        if assigned_sockets:
            reply = QMessageBox.question(
                self, 
                messages.DLG_CONFIRM_TITLE,
                messages.DLG_CONFIRM_RESET_SOCKETS.format(count=len(assigned_sockets)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            
            # 清除旧的关联
            for s in sockets:
                if s.uncontrolled_unit_id:
                    old_unit = self.system.units.get(s.uncontrolled_unit_id)
                    if old_unit:
                        if s.id in old_unit.member_node_ids:
                            old_unit.member_node_ids.remove(s.id)
                        # 如果旧单元空了，标记删除（稍后处理，避免迭代时删除）
                    s.uncontrolled_unit_id = None

            # 清理空单元
            empty_units = [u_id for u_id, u in self.system.units.items() 
                           if u.unit_type == "非受控" and not u.member_node_ids]
            for u_id in empty_units:
                del self.system.units[u_id]

        # 3. 创建新单元
        # 这里简化逻辑：创建一个大的非受控单元包含所有插座
        # 实际工程中可能需要分回路，但在本演示中合为一个
        unit_id = self.system.generate_unit_id("非受控")
        name = self.system.generate_unit_name("非受控")
            
        unit = Unit(
            id=unit_id,
            name=name,
            unit_type="非受控",
            description="自动生成的插座回路",
            member_node_ids=[n.id for n in sockets]
        )
        self.system.add_unit(unit)
        
        for s in sockets:
            s.uncontrolled_unit_id = unit_id
            
        self.refresh_list()
        QMessageBox.information(self, messages.DLG_INFO_TITLE if hasattr(messages, 'DLG_INFO_TITLE') else messages.DLG_WARNING_TITLE, 
                                messages.MSG_UNIT_CREATED_SOCKETS.format(unit_name=unit.name, count=len(sockets)))

    def define_controlled(self):
        """交互式定义受控单元"""
        switches = [n for n in self.system.nodes.values() if n.node_type == NodeType.SWITCH]
        if not switches:
            QMessageBox.information(self, messages.DLG_WARNING_TITLE, messages.MSG_NO_SWITCHES)
            return

        defined_count = 0
        
        processed_any = False
        for switch in switches:
            if not switch.gangs:
                continue
                
            for i in range(1, switch.gangs + 1):
                # 检查该按键是否已经控制了单元
                existing_unit = next((u for u in self.system.units.values() 
                                    if u.control_switch_id == switch.id and u.switch_gang_index == i), None)
                
                if existing_unit:
                    continue

                # 查找未分配的电器（灯具/插座），且未归属于非受控单元
                available_lights = [
                    n for n in self.system.nodes.values() 
                    if n.node_type in (NodeType.LIGHT, NodeType.SOCKET) and n.controlled_unit_id is None and n.uncontrolled_unit_id is None
                ]
                
                if not available_lights:
                    if not processed_any:
                         QMessageBox.information(self, messages.DLG_INFO_TITLE if hasattr(messages, 'DLG_INFO_TITLE') else messages.DLG_WARNING_TITLE, messages.MSG_NO_MORE_DEVICES)
                    return

                dlg = UnitDefinitionDialog(switch, i, available_lights, self)
                if dlg.exec():
                    selected_ids = dlg.get_selected_light_ids()
                    if selected_ids:
                        unit_id = self.system.generate_unit_id("受控")
                        unit_name = f"{switch.label}_按键{i}"
                        unit = Unit(
                            id=unit_id,
                            name=unit_name,
                            unit_type="受控",
                            description=f"由 {switch.label} 控制",
                            member_node_ids=selected_ids,
                            control_switch_id=switch.id,
                            switch_gang_index=i
                        )
                        self.system.add_unit(unit)
                        
                        for light_id in selected_ids:
                            self.system.nodes[light_id].controlled_unit_id = unit_id
                            
                        defined_count += 1
                        processed_any = True
                else:
                    # 用户取消，停止后续定义
                    self.refresh_list()
                    return
        
        self.refresh_list()
        if defined_count > 0:
            QMessageBox.information(self, messages.DLG_INFO_TITLE if hasattr(messages, 'DLG_INFO_TITLE') else messages.DLG_WARNING_TITLE, messages.MSG_UNIT_DEFINED.format(count=defined_count))
        elif not processed_any:
             QMessageBox.information(self, messages.DLG_INFO_TITLE if hasattr(messages, 'DLG_INFO_TITLE') else messages.DLG_WARNING_TITLE, messages.MSG_ALL_DEFINED_OR_NO_DEVICES)

    def edit_unit(self):
        """编辑选中单元"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return
            
        unit_id = current_item.data(Qt.ItemDataRole.UserRole)
        unit = self.system.units.get(unit_id)
        
        if not unit:
            return
            
        if unit.unit_type == "非受控":
            QMessageBox.information(self, messages.DLG_WARNING_TITLE, "非受控单元（插座）请使用'自动识别'功能重新生成。")
            return
            
        if unit.unit_type == "受控":
            # 1. 获取控制开关
            switch = self.system.nodes.get(unit.control_switch_id)
            if not switch:
                QMessageBox.warning(self, messages.DLG_ERROR_TITLE, "找不到关联的开关节点。")
                return
                
            # 2. 准备灯具列表 (当前成员 + 其他未分配的灯具)
            current_members = []
            for node_id in unit.member_node_ids:
                node = self.system.nodes.get(node_id)
                if node:
                    current_members.append(node)
            
            other_available = [
                n for n in self.system.nodes.values() 
                if n.node_type in (NodeType.LIGHT, NodeType.SOCKET) and n.controlled_unit_id is None and n.uncontrolled_unit_id is None
            ]
            
            all_options = current_members + other_available
            initial_selection = [n.id for n in current_members]
            
            # 3. 打开对话框
            dlg = UnitDefinitionDialog(switch, unit.switch_gang_index, all_options, self, initial_selection)
            if dlg.exec():
                selected_ids = dlg.get_selected_light_ids()
                
                # 4. 更新单元
                # 先清除旧成员的关联
                for node_id in unit.member_node_ids:
                    node = self.system.nodes.get(node_id)
                    if node:
                        node.controlled_unit_id = None
                        
                # 更新成员列表
                unit.member_node_ids = selected_ids
                
                # 设置新成员的关联
                for node_id in selected_ids:
                    node = self.system.nodes.get(node_id)
                    if node:
                        node.controlled_unit_id = unit.id
                
                self.refresh_list()
                QMessageBox.information(self, messages.DLG_INFO_TITLE if hasattr(messages, 'DLG_INFO_TITLE') else messages.DLG_WARNING_TITLE, "单元更新成功")
