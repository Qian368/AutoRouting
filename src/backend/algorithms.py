
import networkx as nx
import math
from typing import List, Set, Dict
from .models import CircuitSystem, NodeType, WireType, Node, Conduit, Wire

class WiringCalculator:
    def __init__(self, system: CircuitSystem):
        self.system = system
        self.graph = nx.Graph()
        self._build_graph()

    def _build_graph(self):
        """将系统模型转换为NetworkX图"""
        self.graph.clear()
        for node in self.system.nodes.values():
            self.graph.add_node(node.id, obj=node)
        
        for conduit in self.system.conduits.values():
            self.graph.add_edge(
                conduit.start_node_id, 
                conduit.end_node_id, 
                weight=conduit.length,
                id=conduit.id
            )

    def calculate(self):
        """执行四步法布线计算（按用户定义的回路对象分别执行）"""
        self.system.clear_wires()
        if not self.system.circuits:
            # 回退：按配电箱遍历
            dist_boxes = self.system.distribution_box_ids or ([self.system.distribution_box_id] if self.system.distribution_box_id else [])
            for dbid in dist_boxes:
                allowed = set([dbid]) | set(nid for nid in self.system.nodes.keys())
                circuit_tag = f"{self.system.circuit_id}:{dbid}"
                self._step1_lay_base_circuit(dbid, circuit_tag, allowed)
                self._step2_lay_uncontrolled_power(dbid, circuit_tag, allowed)
                self._step3_lay_control_wires(dbid, circuit_tag, allowed)                
                self._step4_connect_switches_to_power(dbid, circuit_tag, allowed)
            return
        for circuit in self.system.circuits.values():
            dbid = circuit.distribution_box_id
            allowed = set(circuit.member_node_ids) | {dbid}
            circuit_tag = circuit.id
            self._step1_lay_base_circuit(dbid, circuit_tag, allowed)
            self._step2_lay_uncontrolled_power(dbid, circuit_tag, allowed)
            self._step3_lay_control_wires(dbid, circuit_tag, allowed)
            self._step4_connect_switches_to_power(dbid, circuit_tag, allowed)

    def _add_wires_to_path(self, path: List[str], wire_type: WireType, unit_id: str | None = None, circuit_id: str | None = None):
        """在路径上的所有导管添加指定类型的导线"""
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            conduit = self.system.get_conduit(u, v)
            if conduit:
                conduit.add_wire(wire_type, unit_id=unit_id, circuit_id=circuit_id or self.system.circuit_id)

    def _build_wire_graph(self, wire_type: WireType, circuit_id: str | None = None) -> nx.Graph:
        """构建仅包含指定类型导线的图，用于按导线最短路径累加电流（可按回路过滤）"""
        G = nx.Graph()
        for node_id in self.system.nodes.keys():
            G.add_node(node_id)
        for conduit in self.system.conduits.values():
            if any((w.wire_type == wire_type) and ((circuit_id is None) or (w.circuit_id == circuit_id)) for w in conduit.wires):
                G.add_edge(conduit.start_node_id, conduit.end_node_id, weight=conduit.length)
        return G

    def _lay_mst_wires_via_conduits(self, node_ids: List[str], anchor_id: str, wire_type: WireType, unit_id: str | None = None, circuit_id: str | None = None, allowed_nodes: Set[str] | None = None):
        """
        基于现有导管作为基础（不是直线距离）：
        - 在 node_ids + anchor_id 的集合上，以导管图最短路径距离构造完全图
        - 计算该完全图的 MST
        - 对 MST 每条边，沿基础导管图的最短路径铺设指定类型导线
        """
        targets = list(set(node_ids + [anchor_id]))
        if len(targets) < 2:
            return
        # 完全图，边权为基础导管图上的最短路径长度
        K = nx.Graph()
        for i, u in enumerate(targets):
            for j, v in enumerate(targets):
                if i < j:
                    try:
                        baseG = self.graph if not allowed_nodes else self.graph.subgraph(allowed_nodes)
                        dist = nx.shortest_path_length(baseG, u, v, weight='weight')
                        K.add_edge(u, v, weight=dist)
                    except nx.NetworkXNoPath:
                        continue
        if K.number_of_edges() == 0:
            return
        T = nx.minimum_spanning_tree(K, weight='weight')
        for u, v in T.edges():
            try:
                baseG = self.graph if not allowed_nodes else self.graph.subgraph(allowed_nodes)
                p = nx.shortest_path(baseG, source=u, target=v, weight='weight')
                self._add_wires_to_path(p, wire_type, unit_id=unit_id, circuit_id=circuit_id)
            except nx.NetworkXNoPath:
                continue

    def _nearest_db(self, node_id: str, allowed_nodes: Set[str] | None = None) -> str | None:
        """查找指定节点最近的配电箱"""
        dist_boxes = self.system.distribution_box_ids or ([self.system.distribution_box_id] if self.system.distribution_box_id else [])
        best_db = None
        best_dist = float('inf')
        for dbid in dist_boxes:
            try:
                baseG = self.graph if not allowed_nodes else self.graph.subgraph(allowed_nodes | {dbid, node_id})
                d = nx.shortest_path_length(baseG, node_id, dbid, weight='weight')
                if d < best_dist:
                    best_dist = d
                    best_db = dbid
            except nx.NetworkXNoPath:
                continue
        return best_db

    def _step1_lay_base_circuit(self, dbid: str, circuit_id: str, allowed_nodes: Set[str]):
        # 在所有非开关端点的导管铺设 N 与 PE（每个回路各自铺设一套）
        for conduit in self.system.conduits.values():
            u = self.system.nodes.get(conduit.start_node_id)
            v = self.system.nodes.get(conduit.end_node_id)
            if not u or not v:
                continue
            if u.node_type == NodeType.SWITCH or v.node_type == NodeType.SWITCH:
                continue
            if (u.id in allowed_nodes) and (v.id in allowed_nodes):
                conduit.add_wire(Wire(id=f"{conduit.id}-auto-N", wire_type=WireType.N, circuit_id=circuit_id))
                conduit.add_wire(Wire(id=f"{conduit.id}-auto-PE", wire_type=WireType.PE, circuit_id=circuit_id))
        # 沿 N 线为属于该回路的设备累加电流（设备按最近配电箱归属）
        devices = [n for n in self.system.nodes.values() if n.node_type not in (NodeType.SWITCH, NodeType.DISTRIBUTION_BOX) and n.id in allowed_nodes]
        for dev in devices:
            if self._nearest_db(dev.id, allowed_nodes) != dbid:
                continue
            try:
                baseG = self.graph.subgraph(allowed_nodes | {dbid})
                path = nx.shortest_path(baseG, dev.id, dbid, weight='weight')
            except nx.NetworkXNoPath:
                path = None
            if not path:
                continue
            for i in range(len(path) - 1):
                u_id, v_id = path[i], path[i+1]
                conduit = self.system.get_conduit(u_id, v_id)
                if not conduit:
                    continue
                for w in conduit.wires:
                    if w.wire_type == WireType.N and w.circuit_id == circuit_id:
                        w.current += dev.rated_current
    def _step2_lay_uncontrolled_power(self, dbid: str, circuit_id: str, allowed_nodes: Set[str]):
        """
        步骤2：对于非受控单元：
        1、非受控单元，同理和配电箱节点（即把配电箱节点添加到非受控单元的成员节点一起）基于现有的导管作为基础（不是直线距离）采用最小生成树计算后，沿着导管敷电源火线。
        2、对于每个非受控节点沿着电源火线向其配电箱节点找最短路径。在最短路径中，每段导线的电流 = 原导线电流 + 本电器节点的额定电流。
        """
        if not dbid:
            return

        for unit in self.system.units.values():
            if unit.unit_type != "非受控":
                continue
            if not unit.member_node_ids:
                continue
            if not all(mid in allowed_nodes for mid in unit.member_node_ids):
                continue
            member_ids = unit.member_node_ids
            # 1. 铺设电源线 (L_电源)
            self._lay_mst_wires_via_conduits(member_ids, dbid, WireType.L_POWER, unit_id=unit.id, circuit_id=circuit_id, allowed_nodes=allowed_nodes)
            
            # 2. 计算电流
            Gp = self._build_wire_graph(WireType.L_POWER, circuit_id=circuit_id)
            for member_id in member_ids:
                try:
                    path = nx.shortest_path(Gp, source=member_id, target=dbid, weight='weight')
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                
                member_node = self.system.nodes.get(member_id)
                if not member_node:
                    continue
                
                for i in range(len(path) - 1):
                    u, v = path[i], path[i+1]
                    conduit = self.system.get_conduit(u, v)
                    if not conduit:
                        continue
                    # 累加到 L_POWER (这里不区分 unit_id，因为 L_POWER 是公用的？
                    # 不，按文档描述，每个非受控单元铺设自己的 L_POWER。
                    # 但如果是同一个回路，是否共用线？
                    # 文档：每段导线的电流 = 原导线电流 + 本电器节点的额定电流。
                    # 意味着如果多条路径重合，电流会叠加。
                    for w in conduit.wires:
                        if w.wire_type == WireType.L_POWER and w.unit_id == unit.id and w.circuit_id == circuit_id:
                            w.current += member_node.rated_current
    def _step3_lay_control_wires(self, dbid: str, circuit_id: str, allowed_nodes: Set[str]):
        """
        步骤3：对于每个受控单元：
        1、每个受控单元和其匹配的开关节点（即把匹配的开关节点添加到受控单元的成员节点一起）基于现有的导管作为基础（不是直线距离）采用最小生成树计算后，沿着导管敷设控制线。
        2、对于每个受控节点沿着控制线向其开关节点找最短路径。在最短路径中，每段导线的电流 = 原导线电流 + 本电器节点的额定电流。
        3、开关节点的额定电流等于其连接的控制线电流之和。
        """
        for unit in self.system.units.values():
            if unit.unit_type != "受控" or not unit.control_switch_id:
                continue
            if unit.control_switch_id not in allowed_nodes:
                continue
            member_ids = unit.member_node_ids
            if not member_ids:
                continue
            if not all(mid in allowed_nodes for mid in member_ids):
                continue
            switch_id = unit.control_switch_id
            self._lay_mst_wires_via_conduits(member_ids, switch_id, WireType.L_CONTROL, unit_id=unit.id, circuit_id=circuit_id, allowed_nodes=allowed_nodes)
            Gc = self._build_wire_graph(WireType.L_CONTROL, circuit_id=circuit_id)
            for member_id in member_ids:
                try:
                    path = nx.shortest_path(Gc, source=member_id, target=switch_id, weight='weight')
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                member_node = self.system.nodes.get(member_id)
                if not member_node:
                    continue
                for i in range(len(path) - 1):
                    u, v = path[i], path[i+1]
                    conduit = self.system.get_conduit(u, v)
                    if not conduit:
                        continue
                    for w in conduit.wires:
                        if w.wire_type == WireType.L_CONTROL and w.unit_id == unit.id and w.circuit_id == circuit_id:
                            w.current += member_node.rated_current
            
        # 3. 更新开关额定电流
        for switch in self.system.nodes.values():
            if switch.node_type == NodeType.SWITCH:
                total_current = 0.0
                # 统计所有连接到该开关的 L_CONTROL 导线的电流
                # 注意：导线是存在于导管中的，需要遍历开关连接的导管
                for neighbor_id, conduit_id in self.system.adj.get(switch.id, {}).items():
                    if (switch.id not in allowed_nodes) or (neighbor_id not in allowed_nodes):
                        continue
                    conduit = self.system.conduits.get(conduit_id)
                    if not conduit:
                        continue
                    for w in conduit.wires:
                        # 只有流入/流出开关的控制线才算。
                        # 这里简化处理：所有连接到开关的 L_CONTROL 导线电流之和。
                        # 但要注意，如果开关是中间节点，电流会重复计算吗？
                        # 对于 L_CONTROL，开关是汇聚点（根节点），所以连接到它的导线电流即为分支电流。
                        # 求和所有连接导管的 L_CONTROL 电流即可。
                        if w.wire_type == WireType.L_CONTROL and w.circuit_id == circuit_id:
                            total_current += w.current
                switch.rated_current = total_current
    def _step4_connect_switches_to_power(self, dbid: str, circuit_id: str, allowed_nodes: Set[str]):
        """
        步骤4：
        1、各个开关节点就近原则查找电源火线经过节点或者配电箱节点引入电源，敷设电源火线。
        2、对于每个开关节点沿着电源火线向其配电箱节点找最短路径。在最短路径中，每段导线的电流 = 原导线电流 + 本电器节点的额定电流。
        """
        # 初始电源点：当前配电箱 + 本回路已有 L_POWER 的节点
        power_sources = {dbid}
        for conduit in self.system.conduits.values():
            if any((w.wire_type == WireType.L_POWER and w.circuit_id == circuit_id) for w in conduit.wires):
                power_sources.add(conduit.start_node_id)
                power_sources.add(conduit.end_node_id)
        
        switches = [n for n in self.system.nodes.values() if n.node_type == NodeType.SWITCH and n.id in allowed_nodes]
        
        # 迭代连接开关，允许 daisy-chaining (开关连开关)
        # 每次连接一个开关后，它也成为潜在的电源点
        
        # 为了处理依赖顺序，可以使用未连接集合
        unconnected_switches = set(s.id for s in switches)
        
        while unconnected_switches:
            best_switch_id = None
            best_source_id = None
            best_path = None
            best_dist = float('inf')
            
            # 寻找距离现有电源网最近的未连接开关
            for sw_id in unconnected_switches:
                # 如果开关已经在 power_sources 里（例如它也是非受控单元成员？不常见），直接移除
                if sw_id in power_sources:
                    best_switch_id = sw_id
                    best_source_id = sw_id # Self is source
                    best_dist = 0
                    best_path = [sw_id]
                    break
                
                for src_id in power_sources:
                    try:
                        baseG = self.graph.subgraph(allowed_nodes | power_sources)
                        dist = nx.shortest_path_length(baseG, sw_id, src_id, weight='weight')
                        if dist < best_dist:
                            best_dist = dist
                            best_switch_id = sw_id
                            best_source_id = src_id
                            best_path = nx.shortest_path(baseG, sw_id, src_id, weight='weight')
                    except nx.NetworkXNoPath:
                        continue
            
            if best_switch_id is None:
                # 无法连接剩余开关
                print(f"警告：无法连接剩余开关到电源: {unconnected_switches}")
                break
                
            # 连接
            if best_dist > 0:
                self._add_wires_to_path(best_path, WireType.L_POWER, circuit_id=circuit_id)
            
            unconnected_switches.remove(best_switch_id)
            
            # 更新电源源点集合：新路径上的所有点都成为电源源点
            if best_path:
                power_sources.update(best_path)
        
        # 2. 计算电流
        # 此时所有开关都已接入 L_POWER 网络。
        # 对每个开关，计算其负载（rated_current），沿 L_POWER 网络回溯到配电箱。
        
        Gp = self._build_wire_graph(WireType.L_POWER, circuit_id=circuit_id)
        
        for switch in switches:
            if switch.rated_current <= 0:
                continue
                
            try:
                best_path = nx.shortest_path(Gp, switch.id, dbid, weight='weight')
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                best_path = None
            if best_path:
                # 沿路径累加电流
                for i in range(len(best_path) - 1):
                    u, v = best_path[i], best_path[i+1]
                    conduit = self.system.get_conduit(u, v)
                    if not conduit:
                        continue
                    for w in conduit.wires:
                        if w.wire_type == WireType.L_POWER and w.circuit_id == circuit_id:
                            w.current += switch.rated_current

class TopologyGenerator:
    """
    辅助类：用于自动生成物理导管拓扑
    """
    @staticmethod
    def generate_mst_topology(system: CircuitSystem):
        """
        基于当前节点位置，按“回路对象”分别计算欧几里得最小生成树(MST)，并生成导管连接。
        不会删除现有导管，只会添加不存在的连接。新导管绑定 circuit_id，禁止跨回路共享导管。
        """
        if not system.circuits:
            return 0
        total = 0
        for circuit in system.circuits.values():
            allowed_nodes = [system.nodes[nid] for nid in circuit.member_node_ids if nid in system.nodes]
            # 包含配电箱
            db = system.nodes.get(circuit.distribution_box_id)
            if db:
                allowed_nodes.append(db)
            # 排除开关节点（导管以设备/箱/盒为主）
            nodes = [n for n in allowed_nodes if n.node_type != NodeType.SWITCH]
            if len(nodes) < 2:
                continue
            # 1. 构建完全图
            G = nx.Graph()
            for i, u in enumerate(nodes):
                for j, v in enumerate(nodes):
                    if i < j:
                        dist = math.hypot(u.x - v.x, u.y - v.y)
                        G.add_edge(u.id, v.id, weight=dist)
            # 2. 计算MST
            mst = nx.minimum_spanning_tree(G, weight='weight')
            # 3. 转换为导管（绑定回路）
            count = 0
            for u_id, v_id in mst.edges():
                # 检查是否已存在同回路连接（无向）
                exists = False
                for conduit in system.conduits.values():
                    if conduit.circuit_id == circuit.id and \
                       ((conduit.start_node_id == u_id and conduit.end_node_id == v_id) or \
                        (conduit.start_node_id == v_id and conduit.end_node_id == u_id)):
                        exists = True
                        break
                if not exists:
                    conduit_id = f"c_{circuit.id}_{len(system.conduits) + 1}_{count}"
                    conduit = Conduit(id=conduit_id, start_node_id=u_id, end_node_id=v_id, circuit_id=circuit.id)
                    system.add_conduit(conduit)
                    count += 1
            total += count
            # 4. 为该回路内每个受控单元连接最近成员到匹配开关（同回路）
            for unit in system.units.values():
                if unit.unit_type == "受控" and unit.control_switch_id and unit.member_node_ids:
                    if unit.control_switch_id not in circuit.member_node_ids:
                        continue
                    if not all(mid in circuit.member_node_ids for mid in unit.member_node_ids):
                        continue
                    switch = system.nodes.get(unit.control_switch_id)
                    if not switch:
                        continue
                    best_member = None
                    best_dist = float('inf')
                    for mid in unit.member_node_ids:
                        m = system.nodes.get(mid)
                        if not m:
                            continue
                        d = math.hypot(m.x - switch.x, m.y - switch.y)
                        if d < best_dist:
                            best_dist = d
                            best_member = m
                    if best_member:
                        exists = False
                        for conduit in system.conduits.values():
                            if conduit.circuit_id == circuit.id and \
                               ((conduit.start_node_id == best_member.id and conduit.end_node_id == switch.id) or \
                                (conduit.start_node_id == switch.id and conduit.end_node_id == best_member.id)):
                                exists = True
                                break
                        if not exists:
                            conduit_id = f"c_{circuit.id}_{len(system.conduits) + 1}_{count}"
                            conduit = Conduit(id=conduit_id, start_node_id=best_member.id, end_node_id=switch.id, circuit_id=circuit.id)
                            system.add_conduit(conduit)
                            count += 1
            total += 0  # 已计入 count
        return total
