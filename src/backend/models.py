from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Union
import math

# ---------- 基础枚举定义 ----------
class NodeType(Enum):
    DISTRIBUTION_BOX = "配电箱"     # 电源起点
    SWITCH = "开关"       # 控制节点
    LIGHT = "灯具"       # 受控设备
    SOCKET = "插座"       # 非受控设备
    JUNCTION_BOX = "接线盒"      # 纯连接节点

class WireType(Enum):
    N = "N"          # 零线
    PE = "PE"         # 保护地线
    L_UNIT = "L_单元"     # 单元内部并联火线
    L_CONTROL = "L_控制"     # 控制线（从单元到开关）
    L_POWER = "L_电源"      # 电源线（从电源点到开关或从非受控单元到配电箱）

# ---------- 核心数据结构 ----------
# ---------- 导线对象 ----------
@dataclass
class Wire:
    id: str
    wire_type: WireType
    unit_id: Optional[str] = None
    circuit_id: Optional[str] = None
    current: float = 0.0
    path: List[str] = field(default_factory=list)  # 该导线依次穿过的导管段ID列表
    color: str = ""  # 用于图纸标注的颜色名称，如"红色","蓝色"

# ---------- 导管对象 ----------
@dataclass
class Conduit:
    id: str
    start_node_id: str
    end_node_id: str
    length: float = 0.0
    wires: List[Wire] = field(default_factory=list) # 穿行导线列表
    circuit_id: Optional[str] = None
    
    def add_wire(self, wire: Union[WireType, Wire], count: int = 1, unit_id: Optional[str] = None, circuit_id: Optional[str] = None):
        """添加指定类型的导线到导管"""
        def _color_for(wt: WireType) -> str:
            if wt == WireType.N:
                return "蓝色"
            if wt == WireType.PE:
                return "黄绿"
            if wt == WireType.L_CONTROL:
                return "橙色"
            if wt == WireType.L_POWER:
                return "红色"
            if wt == WireType.L_UNIT:
                return "棕色"
            return "黑色"
        # 处理WireType枚举值
        # 如果提供了 circuit_id，则绑定导管所属回路；若导管已绑定其它回路，拒绝混穿
        if circuit_id:
            if self.circuit_id is None:
                self.circuit_id = circuit_id
            elif self.circuit_id != circuit_id:
                raise ValueError(f"不同回路的导线不能穿在同一根导管上（导管{self.id}属于{self.circuit_id}, 当前为{circuit_id}）")
        if isinstance(wire, WireType):
            for i in range(count):
                wid = f"{self.id}-w-{len(self.wires) + 1 + i}"
                self.wires.append(Wire(
                    id=wid,
                    wire_type=wire,
                    unit_id=unit_id,
                    circuit_id=circuit_id or self.circuit_id,
                    current=0.0,
                    path=[self.id],
                    color=_color_for(wire),
                ))         
        else:
            for i in range(count):
                wid = f"{self.id}-w-{len(self.wires) + 1 + i}"
                self.wires.append(Wire(
                    id=wid,
                    wire_type=wire.wire_type,
                    unit_id=wire.unit_id,
                    circuit_id=wire.circuit_id or self.circuit_id,
                    current=wire.current,
                    path=[self.id] if not wire.path else wire.path,
                    color=wire.color or _color_for(wire.wire_type),
                ))

# ---------- 节点对象 ----------
@dataclass
class Node:
    id: str
    node_type: NodeType
    x: float
    y: float
    label: str
    
    # 设备特定属性
    gangs: Optional[int] = None  # 开关联数
    power: Optional[float] = None # 额定功率
    rated_current: float = 0.0
    usage: Optional[str] = None   # 用途
    
    # 单元关联信息 (在运行时填充)
    controlled_unit_id: Optional[str] = None # 所属受控单元ID
    uncontrolled_unit_id: Optional[str] = None # 所属非受控单元ID
    
    connected_wires: List[Wire] = field(default_factory=list)
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.id == other.id

# ---------- 单元对象 ----------
@dataclass
class Unit:
    id: str
    name: str
    unit_type: str # "受控" 或 "非受控"
    description: str
    member_node_ids: List[str] = field(default_factory=list)
    
    # 受控单元特有
    control_switch_id: Optional[str] = None
    switch_gang_index: Optional[int] = None

@dataclass
class Circuit:
    id: str
    name: str
    distribution_box_id: str
    member_node_ids: List[str] = field(default_factory=list)

# ---------- 回路系统对象 ----------
class CircuitSystem:
    def __init__(self):
        self.nodes: Dict[str, Node] = {} # id -> Node
        self.conduits: Dict[str, Conduit] = {} # id -> Conduit
        self.units: Dict[str, Unit] = {} # id -> Unit
        self.distribution_box_id: Optional[str] = None
        self.distribution_box_ids: List[str] = []
        self.circuit_id: str = "回路001"
        self.circuits: Dict[str, Circuit] = {}
        
        # 邻接表，用于图算法
        # node_id -> {neighbor_id -> conduit_id}
        self.adj: Dict[str, Dict[str, str]] = {}

    def add_node(self, node: Node):
        self.nodes[node.id] = node
        if node.node_type == NodeType.DISTRIBUTION_BOX:
            self.distribution_box_ids.append(node.id)
            if self.distribution_box_id is None:
                self.distribution_box_id = node.id
        if node.id not in self.adj:
            self.adj[node.id] = {}

    def add_conduit(self, conduit: Conduit):
        self.conduits[conduit.id] = conduit
        
        # 更新邻接表
        if conduit.start_node_id not in self.adj:
            self.adj[conduit.start_node_id] = {}
        if conduit.end_node_id not in self.adj:
            self.adj[conduit.end_node_id] = {}
            
        self.adj[conduit.start_node_id][conduit.end_node_id] = conduit.id
        self.adj[conduit.end_node_id][conduit.start_node_id] = conduit.id
        
        # 计算长度
        n1 = self.nodes.get(conduit.start_node_id)
        n2 = self.nodes.get(conduit.end_node_id)
        if n1 and n2:
            conduit.length = math.sqrt((n1.x - n2.x)**2 + (n1.y - n2.y)**2)

    def add_unit(self, unit: Unit):
        self.units[unit.id] = unit

    def add_circuit(self, circuit: Circuit):
        self.circuits[circuit.id] = circuit
        if circuit.distribution_box_id not in self.distribution_box_ids:
            self.distribution_box_ids.append(circuit.distribution_box_id)
            if self.distribution_box_id is None:
                self.distribution_box_id = circuit.distribution_box_id
        for nid in circuit.member_node_ids:
            if nid not in self.nodes:
                continue
            # 非配电箱节点只能属于一个回路
            n = self.nodes[nid]
            if n.node_type != NodeType.DISTRIBUTION_BOX:
                # 检查是否已在其他回路
                for c in self.circuits.values():
                    if c.id != circuit.id and nid in c.member_node_ids:
                        raise ValueError(f"节点 {nid} 已属于回路 {c.id}，不能重复加入")
        return circuit.id

    def assign_node_to_circuit(self, node_id: str, circuit_id: str):
        if circuit_id not in self.circuits or node_id not in self.nodes:
            return
        circuit = self.circuits[circuit_id]
        node = self.nodes[node_id]
        if node.node_type != NodeType.DISTRIBUTION_BOX:
            for c in self.circuits.values():
                if c.id != circuit_id and node_id in c.member_node_ids:
                    raise ValueError(f"节点 {node_id} 已属于回路 {c.id}，不能重复加入")
        if node_id not in circuit.member_node_ids:
            circuit.member_node_ids.append(node_id)
    
    def ensure_default_single_circuit(self):
        if self.circuits:
            return
        if len(self.distribution_box_ids) != 1:
            return
        dbid = self.distribution_box_ids[0]
        member_ids = [nid for nid in self.nodes.keys() if nid != dbid]
        if not member_ids:
            return
        cid = self.circuit_id or "回路001"
        if cid in self.circuits:
            return
        circuit = Circuit(id=cid, name=cid, distribution_box_id=dbid, member_node_ids=member_ids)
        self.add_circuit(circuit)

    def generate_unit_id(self, unit_type: str) -> str:
        """生成单元ID（受控：C-UTx，非受控：U-UTx），使用最小缺失序号"""
        prefix = "C-UT" if unit_type == "受控" else "U-UT"
        # 查找现有ID的最大序号及缺口
        existing_ids = [uid for uid in self.units.keys() if uid.startswith(prefix)]
        existing_seqs = {int(uid[len(prefix):]) for uid in existing_ids if uid[len(prefix):].isdigit()}
        max_seq = max(existing_seqs) if existing_seqs else 0
        all_seqs = set(range(1, max_seq + 2))
        missing = all_seqs - existing_seqs
        seq = min(missing) if missing else max_seq + 1
        return f"{prefix}{seq}"

    def generate_unit_name(self, unit_type: str) -> str:
        """生成单元名称，独立自增"""
        prefix = "受控单元" if unit_type == "受控" else "非受控单元"
        existing_names = [u.name for u in self.units.values() if u.name.startswith(prefix)]
        existing_seqs = set()
        for name in existing_names:
            try:
                # 提取前缀后的数字
                num_str = name[len(prefix):].strip()
                if num_str.isdigit():
                    existing_seqs.add(int(num_str))
            except:
                continue
        
        max_seq = max(existing_seqs) if existing_seqs else 0
        all_seqs = set(range(1, max_seq + 2))
        missing = all_seqs - existing_seqs
        seq = min(missing) if missing else max_seq + 1
        return f"{prefix}{seq}"
        
    def generate_circuit_id(self) -> str:
        """生成回路ID（C-Cx），使用最小缺失序号"""
        prefix = "C-C"
        existing_ids = [cid for cid in self.circuits.keys() if cid.startswith(prefix)]
        existing_seqs = {int(cid[len(prefix):]) for cid in existing_ids if cid[len(prefix):].isdigit()}
        max_seq = max(existing_seqs) if existing_seqs else 0
        all_seqs = set(range(1, max_seq + 2))
        missing = all_seqs - existing_seqs
        seq = min(missing) if missing else max_seq + 1
        return f"{prefix}{seq}"

    def generate_circuit_name(self) -> str:
        """生成回路名称，独立自增"""
        prefix = "回路"
        existing_names = [c.name for c in self.circuits.values() if c.name.startswith(prefix)]
        existing_seqs = set()
        for name in existing_names:
            try:
                num_str = name[len(prefix):].strip()
                if num_str.isdigit():
                    existing_seqs.add(int(num_str))
            except:
                continue
        max_seq = max(existing_seqs) if existing_seqs else 0
        all_seqs = set(range(1, max_seq + 2))
        missing = all_seqs - existing_seqs
        seq = min(missing) if missing else max_seq + 1
        return f"{prefix}{seq}"

    def get_neighbors(self, node_id: str) -> List[str]:
        return list(self.adj.get(node_id, {}).keys())

    def get_conduit(self, u_id: str, v_id: str) -> Optional[Conduit]:
        conduit_id = self.adj.get(u_id, {}).get(v_id)
        if conduit_id:
            return self.conduits[conduit_id]
        return None

    def clear_wires(self):
        for conduit in self.conduits.values():
            conduit.wires = []
    
    def rename_node_id(self, old_id: str, new_id: str):
        """重命名节点ID，级联更新所有引用"""
        if not new_id:
            raise ValueError("ID不能为空")
        if old_id == new_id:
            return
        if new_id in self.nodes:
            raise ValueError(f"ID {new_id} 已存在")
        if old_id not in self.nodes:
            raise ValueError(f"节点 {old_id} 不存在")
        node = self.nodes.pop(old_id)
        node.id = new_id
        self.nodes[new_id] = node
        # 更新邻接表键与邻居引用
        neighbors = self.adj.pop(old_id, {})
        self.adj[new_id] = neighbors
        for nb_id, conduit_id in neighbors.items():
            if nb_id in self.adj:
                # 将邻居的映射键从 old_id 改为 new_id
                if old_id in self.adj[nb_id]:
                    self.adj[nb_id][new_id] = self.adj[nb_id].pop(old_id)
        # 更新导管端点
        for c in self.conduits.values():
            if c.start_node_id == old_id:
                c.start_node_id = new_id
            if c.end_node_id == old_id:
                c.end_node_id = new_id
        # 更新配电箱标识
        self.distribution_box_ids = [new_id if i == old_id else i for i in self.distribution_box_ids]
        if self.distribution_box_id == old_id:
            self.distribution_box_id = new_id
        # 更新单元成员与受控开关
        for u in self.units.values():
            u.member_node_ids = [new_id if i == old_id else i for i in u.member_node_ids]
            if u.control_switch_id == old_id:
                u.control_switch_id = new_id
        # 更新回路成员
        for c in self.circuits.values():
            c.member_node_ids = [new_id if i == old_id else i for i in c.member_node_ids]

    def remove_node(self, node_id: str):
        """删除节点及其相连的导管"""
        if node_id not in self.nodes:
            return
        
        # 1. 删除相连的导管
        connected_conduits = []
        for neighbor_id, conduit_id in self.adj.get(node_id, {}).items():
            connected_conduits.append(conduit_id)
        
        for conduit_id in connected_conduits:
            self.remove_conduit(conduit_id)
            
        # 2. 从邻接表中删除
        if node_id in self.adj:
            del self.adj[node_id]
            
        # 3. 删除节点
        del self.nodes[node_id]
        
        # 4. 如果是配电箱，清除标记
        if self.distribution_box_id == node_id:
            self.distribution_box_id = None
            
        # 5. 清理 Unit 中的引用
        for unit in self.units.values():
            if node_id in unit.member_node_ids:
                unit.member_node_ids.remove(node_id)
            if unit.control_switch_id == node_id:
                unit.control_switch_id = None
            
    def remove_conduit(self, conduit_id: str):
        """删除导管"""
        if conduit_id not in self.conduits:
            return
            
        conduit = self.conduits[conduit_id]
        u, v = conduit.start_node_id, conduit.end_node_id
        
        # 更新邻接表
        if u in self.adj and v in self.adj[u]:
            del self.adj[u][v]
        if v in self.adj and u in self.adj[v]:
            del self.adj[v][u]
            
        del self.conduits[conduit_id]

    def clear_nodes(self):
        """清空所有节点（级联清空导管和单元）"""
        self.nodes.clear()
        self.conduits.clear()
        self.adj.clear()
        self.units.clear()
        self.distribution_box_id = None
        self.distribution_box_ids = []

    def clear_conduits(self):
        """清空所有导管"""
        self.conduits.clear()
        # 重置邻接表
        self.adj = {}
        for node_id in self.nodes:
            self.adj[node_id] = {}
