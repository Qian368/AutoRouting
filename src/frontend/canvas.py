
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsItem, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QGraphicsSceneMouseEvent, QStyle
from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QLineF
from PyQt6.QtGui import QPen, QBrush, QColor, QFont
from typing import Dict, Optional, List
from src.backend.models import Node, Conduit, NodeType, WireType
from src.common import messages

# ---------- 节点操作类 ----------
class NodeItem(QGraphicsEllipseItem):
    def __init__(self, node: Node, radius=15):
        super().__init__(-radius, -radius, radius*2, radius*2)
        self.node = node
        self.radius = radius
        self.setPos(node.x, node.y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | 
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        # 设置样式
        self.set_style()
        
        # 标签
        self.label_item = QGraphicsTextItem(node.label, self)
        self.label_item.setPos(-radius, radius + 2)
        
    def set_style(self):
        color_map = {
            NodeType.DISTRIBUTION_BOX: QColor("#FF5722"), # Deep Orange
            NodeType.SWITCH: QColor("#2196F3"),           # Blue
            NodeType.LIGHT: QColor("#FFC107"),            # Amber
            NodeType.SOCKET: QColor("#4CAF50"),           # Green
            NodeType.JUNCTION_BOX: QColor("#9E9E9E")      # Grey
        }
        color = color_map.get(self.node.node_type, Qt.GlobalColor.black)
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.GlobalColor.black))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            self.node.x = value.x()
            self.node.y = value.y()
            # 通知场景更新连接线
            if self.scene():
                self.scene().update_conduits(self.node.id)
        return super().itemChange(change, value)

# ---------- 导管操作类 ----------
class ConduitItem(QGraphicsLineItem):
    def __init__(self, conduit: Conduit, start_item: NodeItem, end_item: NodeItem):
        super().__init__()
        self.conduit = conduit
        self.start_item = start_item
        self.end_item = end_item
        self.setZValue(-1) # 在节点下方
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        
        self.text_item = QGraphicsTextItem("", self)
        self.text_item.setDefaultTextColor(QColor("black"))
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        self.text_item.setFont(font)
        
        self.update_position()
        # self.update_style() # Style is handled in paint now

    def update_position(self):
        line = QLineF(self.start_item.pos(), self.end_item.pos())
        self.setLine(line)
        
        # 更新文字位置（中心）
        center = line.center()
        self.text_item.setPos(center)
        self.update_text()

    def update_text(self):
        if not self.conduit.wires:
            self.text_item.setPlainText("")
            return
            
        # 统计导线
        counts = {}
        for w in self.conduit.wires:
            wt = w.wire_type
            counts[wt] = counts.get(wt, 0) + 1
            
        total = len(self.conduit.wires)
        text = f"{total}根\n"
        
        # 简化显示
        details = []
        if WireType.N in counts: details.append("N")
        if WireType.PE in counts: details.append("PE")
        if WireType.L_POWER in counts: details.append("L源")
        if WireType.L_UNIT in counts: details.append("L单")
        if WireType.L_CONTROL in counts: details.append("L控")
        
        # text += ",".join(details)
        self.text_item.setPlainText(text)

    # 处理选中状态变化
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            self.update() # Force repaint
        return super().itemChange(change, value)

    # 绘制导管
    def paint(self, painter, option, widget):
        is_selected = option.state & QStyle.StateFlag.State_Selected
        
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2)
        
        if self.conduit.wires:
            pen.setColor(QColor("#E91E63")) 
            pen.setWidth(3)
            
        if is_selected:
            pen.setColor(QColor("#2196F3"))
            pen.setWidth(4)
            
        self.setPen(pen)
        super().paint(painter, option, widget)

# ---------- 场景对象 ----------
class CircuitScene(QGraphicsScene):
    node_selected = pyqtSignal(object) # 发送 Node 对象
    # 新增信号
    node_create_requested = pyqtSignal(float, float) # x, y
    conduit_requested = pyqtSignal(str, str) # start_id, end_id
    
    def __init__(self, x, y, w, h):
        super().__init__(x, y, w, h)
        self.mode = "select" # select, add_node, add_conduit
        self.current_node_type = None
        
        self.node_items: Dict[str, NodeItem] = {}
        self.conduit_items: Dict[str, ConduitItem] = {}
        
        self.temp_line = None
        self.first_node_id = None # 用于连接导管时的第一个节点

    def reset_temp_state(self):
        """重置临时状态，如正在绘制的导管"""
        self.first_node_id = None
        if self.temp_line:
            self.removeItem(self.temp_line)
            self.temp_line = None

    def add_node_item(self, node: Node):
        item = NodeItem(node)
        self.addItem(item)
        self.node_items[node.id] = item

    def add_conduit_item(self, conduit: Conduit):
        
        if conduit.start_node_id in self.node_items and conduit.end_node_id in self.node_items:
            start_item = self.node_items[conduit.start_node_id]
            end_item = self.node_items[conduit.end_node_id]
            item = ConduitItem(conduit, start_item, end_item)
            self.addItem(item)
            self.conduit_items[conduit.id] = item

    def update_conduits(self, node_id):
        """当节点移动时，更新相关导管的位置"""
        for item in self.conduit_items.values():
            if item.conduit.start_node_id == node_id or item.conduit.end_node_id == node_id:
                item.update_position()

    def update_all_conduits_visuals(self):
        """更新所有导管的可视化元素"""
        # 先更新位置，确保文字在正确位置
        for item in self.conduit_items.values():
            item.update_position()
            
        # 然后更新文字
        for item in self.conduit_items.values():
            item.update_text()
            item.update() # Ensure visual update

    def _get_selectable_item_at(self, pos):
        """获取指定位置的可选顶层项（NodeItem 或 ConduitItem）"""
        item = self.itemAt(pos, self.views()[0].transform())
        if not item:
            return None
        current = item
        while current:
            if isinstance(current, (NodeItem, ConduitItem)):
                return current
            current = current.parentItem()
        return None

    def _get_node_item_at(self, pos):
        """获取指定位置的NodeItem，处理子项（如Label）点击的情况"""
        item = self._get_selectable_item_at(pos)
        return item if isinstance(item, NodeItem) else None
        
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """处理鼠标点击事件"""
        pos = event.scenePos()
        
        if self.mode == "add_node" and self.current_node_type:
            # 发射信号请求创建节点
            self.node_create_requested.emit(pos.x(), pos.y())
            
        elif self.mode == "add_conduit":
            item = self._get_node_item_at(pos)
            
            if item:
                if self.first_node_id is None:
                    # 开始连接
                    self.first_node_id = item.node.id
                    # 创建临时线
                    self.temp_line = QGraphicsLineItem(QLineF(pos, pos))
                    pen = QPen(Qt.GlobalColor.black)
                    pen.setStyle(Qt.PenStyle.DashLine)
                    self.temp_line.setPen(pen)
                    self.addItem(self.temp_line)
                else:
                    # 完成连接
                    if item.node.id != self.first_node_id:
                        # 发送连接信号
                        self.conduit_requested.emit(self.first_node_id, item.node.id)
                    
                    # 重置状态
                    self.first_node_id = None
                    if self.temp_line:
                        self.removeItem(self.temp_line)
                        self.temp_line = None
            else:
                # 点击空白处取消
                self.first_node_id = None
                if self.temp_line:
                    self.removeItem(self.temp_line)
                    self.temp_line = None

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """处理鼠标移动事件"""
        if self.mode == "add_conduit" and self.first_node_id and self.temp_line:
            start_item = self.node_items.get(self.first_node_id)
            if start_item:
                start_pos = start_item.scenePos()
                self.temp_line.setLine(QLineF(start_pos, event.scenePos()))
            
        super().mouseMoveEvent(event)
