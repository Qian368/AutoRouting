from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QListWidget, QAbstractItemView,
                             QMessageBox, QDialogButtonBox, QComboBox, QLineEdit)
from PyQt6.QtCore import Qt
import uuid
from src.backend.models import CircuitSystem, NodeType, Circuit
from src.common import messages

class CircuitManagerDialog(QDialog):
    """回路管理器：用于新增/编辑/删除回路，并维护节点唯一归属"""
    def __init__(self, system: CircuitSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self.main_window = parent
        self.setWindowTitle(messages.DLG_CIRCUIT_MANAGER_TITLE)
        self.resize(520, 420)
        self.layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.layout.addWidget(self.list)
        # 操作按钮
        btns = QHBoxLayout()
        self.btn_add = QPushButton(messages.BTN_CIRCUIT_ADD)
        self.btn_edit = QPushButton(messages.BTN_CIRCUIT_EDIT_MEMBERS)
        self.btn_remove = QPushButton(messages.BTN_CIRCUIT_DELETE)
        self.btn_close = QPushButton(messages.BTN_CLOSE)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_edit)
        btns.addWidget(self.btn_remove)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)
        self.layout.addLayout(btns)
        # 信号连接
        self.btn_add.clicked.connect(self.on_add_circuit)
        self.btn_edit.clicked.connect(self.on_edit_members)
        self.btn_remove.clicked.connect(self.on_delete_circuit)
        self.btn_close.clicked.connect(self.accept)
        # 初始化
        self.refresh_list()

    def refresh_list(self):
        """刷新回路列表"""
        self.list.clear()
        for c in self.system.circuits.values():
            db = self.system.nodes.get(c.distribution_box_id)
            db_label = db.label if db else c.distribution_box_id
            self.list.addItem(f"{c.name} (ID:{c.id}) - 配电箱: {db_label} - 成员数: {len(c.member_node_ids)}")
            item = self.list.item(self.list.count() - 1)
            item.setData(100, c.id)  # UserRole

    def current_circuit(self) -> Circuit | None:
        """获取当前选中回路"""
        item = self.list.currentItem()
        if not item:
            return None
        cid = item.data(100)
        return self.system.circuits.get(cid)

    def on_add_circuit(self):
        """新增回路"""
        dlg = CircuitCreateDialog(self.system, self)
        if dlg.exec():
            name, dbid = dlg.get_data()
            if not name or not dbid:
                QMessageBox.warning(self, messages.DLG_WARNING_TITLE, messages.MSG_CIRCUIT_NAME_OR_DB_EMPTY)
                return
            try:
                # 生成回路ID（顺序ID：CTx，使用最小缺失序号）
                existing_ids = [cid for cid in self.system.circuits.keys() if cid.startswith("CT")]
                existing_seqs = {int(cid[2:]) for cid in existing_ids if cid[2:].isdigit()}
                max_seq = max(existing_seqs) if existing_seqs else 0
                all_seqs = set(range(1, max_seq + 2))
                missing = all_seqs - existing_seqs
                seq = min(missing) if missing else max_seq + 1
                cid = f"CT{seq}"
                circuit = Circuit(id=cid, name=name, distribution_box_id=dbid, member_node_ids=[])
                self.system.add_circuit(circuit)
                QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_CIRCUIT_CREATED.format(name=name))
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, messages.DLG_ERROR_TITLE, str(e))

    def on_edit_members(self):
        """编辑成员节点（加入/移除）"""
        circuit = self.current_circuit()
        if not circuit:
            QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_SELECT_CIRCUIT_FIRST)
            return
        dlg = CircuitMembersDialog(self.system, circuit, self)
        if dlg.exec():
            # 成员更新已在对话框中完成
            self.refresh_list()

    def on_delete_circuit(self):
        """删除选中回路"""
        circuit = self.current_circuit()
        if not circuit:
            return
        reply = QMessageBox.question(self, messages.DLG_CONFIRM_TITLE, messages.DLG_CONFIRM_DELETE_CIRCUIT.format(name=circuit.name),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        # 仅删除回路对象，不改动节点
        try:
            del self.system.circuits[circuit.id]
        except Exception as e:
            QMessageBox.critical(self, messages.DLG_ERROR_TITLE, str(e))
            return
        self.refresh_list()
        QMessageBox.information(self, messages.DLG_INFO_TITLE, messages.MSG_CIRCUIT_DELETED.format(name=circuit.name))

class CircuitCreateDialog(QDialog):
    """创建回路对话框：选择配电箱与命名"""
    def __init__(self, system: CircuitSystem, parent=None):
        super().__init__(parent)
        self.system = system
        self.setWindowTitle(messages.DLG_CIRCUIT_CREATE_TITLE)
        self.resize(360, 180)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(messages.LBL_CIRCUIT_NAME))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)
        layout.addWidget(QLabel(messages.LBL_SELECT_DB))
        self.cmb_db = QComboBox()
        dbs = [n for n in self.system.nodes.values() if n.node_type == NodeType.DISTRIBUTION_BOX]
        for db in dbs:
            self.cmb_db.addItem(f"{db.label} (ID:{db.id})", db.id)
        layout.addWidget(self.cmb_db)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        """返回回路名称与配电箱ID"""
        name = self.name_edit.text().strip()
        dbid = self.cmb_db.currentData()
        return name, dbid

class CircuitMembersDialog(QDialog):
    """编辑回路成员对话框：加入或移除节点"""
    def __init__(self, system: CircuitSystem, circuit: Circuit, parent=None):
        super().__init__(parent)
        self.system = system
        self.circuit = circuit
        self.setWindowTitle(messages.DLG_CIRCUIT_EDIT_TITLE.format(name=circuit.name))
        self.resize(640, 420)
        self.layout = QVBoxLayout(self)
        # 说明
        self.layout.addWidget(QLabel(messages.MSG_CIRCUIT_EDIT_HINT))
        # 可加入节点列表（不含配电箱；且未加入其他回路或已属于当前回路）
        self.list_available = QListWidget()
        self.list_available.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.layout.addWidget(QLabel(messages.LBL_AVAILABLE_NODES))
        self.layout.addWidget(self.list_available)
        # 已有成员列表
        self.list_members = QListWidget()
        self.list_members.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.layout.addWidget(QLabel(messages.LBL_CURRENT_MEMBERS))
        self.layout.addWidget(self.list_members)
        # 操作按钮
        btns = QHBoxLayout()
        self.btn_add = QPushButton(messages.BTN_ADD_TO_CIRCUIT)
        self.btn_remove = QPushButton(messages.BTN_REMOVE_FROM_CIRCUIT)
        self.btn_close = QPushButton(messages.BTN_CLOSE)
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_remove)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)
        self.layout.addLayout(btns)
        # 信号
        self.btn_add.clicked.connect(self.on_add_selected)
        self.btn_remove.clicked.connect(self.on_remove_selected)
        self.btn_close.clicked.connect(self.accept)
        # 初始化
        self.refresh_lists()

    def _node_in_other_circuit(self, node_id: str) -> bool:
        """判断节点是否属于其它回路（配电箱除外）"""
        node = self.system.nodes.get(node_id)
        if not node or node.node_type == NodeType.DISTRIBUTION_BOX:
            return False
        for c in self.system.circuits.values():
            if c.id != self.circuit.id and node_id in c.member_node_ids:
                return True
        return False

    def refresh_lists(self):
        """刷新可选与成员列表"""
        self.list_available.clear()
        self.list_members.clear()
        # 可加入节点：非配电箱，且未在其他回路；已在当前回路也允许显示在右侧
        for n in self.system.nodes.values():
            if n.node_type == NodeType.DISTRIBUTION_BOX:
                continue
            # 允许加入：未在其他回路 或 已经在当前回路
            in_other = self._node_in_other_circuit(n.id)
            if (not in_other) or (n.id in self.circuit.member_node_ids):
                self.list_available.addItem(f"{n.label}（{n.node_type.value}） (ID:{n.id})")
                item = self.list_available.item(self.list_available.count() - 1)
                item.setData(100, n.id)
        # 回路成员
        for nid in self.circuit.member_node_ids:
            node = self.system.nodes.get(nid)
            if node:
                self.list_members.addItem(f"{node.label}（{node.node_type.value}） (ID:{node.id})")
                item = self.list_members.item(self.list_members.count() - 1)
                item.setData(100, node.id)

    def on_add_selected(self):
        """将选中可选节点加入回路（唯一归属约束在后端校验）"""
        selected = self.list_available.selectedItems()
        if not selected:
            return
        errs = []
        for item in selected:
            nid = item.data(100)
            try:
                self.system.assign_node_to_circuit(nid, self.circuit.id)
            except Exception as e:
                errs.append(str(e))
        if errs:
            QMessageBox.warning(self, messages.DLG_WARNING_TITLE, "\n".join(errs))
        self.refresh_lists()

    def on_remove_selected(self):
        """将选中成员从回路移除"""
        selected = self.list_members.selectedItems()
        if not selected:
            return
        for item in selected:
            nid = item.data(100)
            if nid in self.circuit.member_node_ids:
                self.circuit.member_node_ids.remove(nid)
        self.refresh_lists()