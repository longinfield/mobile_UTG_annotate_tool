// app.js —— 与 template/index.html 的新按钮区一致
document.addEventListener('DOMContentLoaded', function () {
  const API_BASE = location.origin.includes('http') ? location.origin : 'http://127.0.0.1:5000';

  const cy = cytoscape({
    container: document.getElementById('cy'),
    elements: [],
    style: [
      { selector: 'node', style: {
          'background-image': 'data(image)',
          'background-fit': 'cover',
          'label': 'data(label)',
          'shape': 'rectangle','width': '250px','height': '500px',
          'font-size': 12,'text-wrap': 'wrap','text-max-width': '240px',
          'text-valign': 'top','text-halign': 'center','padding': '4px','color': '#111'
      }},
      { selector: 'node:selected', style: { 'border-width': 3, 'border-color': 'blue' } },
      { selector: 'edge', style: {
          'width': 2,'line-color': '#ccc','target-arrow-color': '#ccc',
          'target-arrow-shape': 'triangle','curve-style': 'bezier',
          'label': 'data(label)','font-size': 12,'text-rotation': 'autorotate','text-margin-y': -10,'color': '#333'
      }},
      { selector: 'edge:selected', style: { 'line-color': 'blue', 'width': 4, 'target-arrow-color': 'blue' } }
    ],
    layout: { name: 'grid', fit: true, padding: 20 }
  });

  let visitList = [], utg = [], leafJSON = [], vhJSON = [];
  const BBOX_THRESHOLD = 10;
  let addedEdges = new Set(); // 用于存储已添加的边 ID

  const $ = id => document.getElementById(id);
  const pathInput  = $('folder-path');
  const pickBtn    = $('pick-folder');
  const refreshBtn = $('refresh-btn');
  const mergeBtn   = $('merge-nodes-btn');
  const saveBtn    = $('save-batch-btn');
  const downloadBtn= $('download-btn');

  async function savePositionsToBackend() {
    const positions = {};
    cy.nodes().forEach(n => { positions[n.data('label')] = n.position(); });
    await fetch(`${API_BASE}/api/save-positions`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ positions })
    }).catch(e => console.error('save-positions failed', e));
  }
  let posTimer=null;
  cy.on('position','node',()=>{ clearTimeout(posTimer); posTimer=setTimeout(savePositionsToBackend,400); });

  function buildGraphFromBackend(data){
    cy.elements().remove();
    leafJSON = data.leafJSON||[];
    vhJSON = data.vhJSON||[];
    visitList= data.visitList||[];
    utg = data.utg||[];

    const nodes=(data.nodes||[]).map(n=>({
      data:{ id:n.id,label:n.label,image:n.imageUrl }, ...(n.position?{position:n.position}:{})
    }));
    cy.add(nodes);

    for (let i = 0; i < utg.length; i++) {
        const links = utg[i] || [], src = `${i}_screenshot.jpg`;
        for (const l of links) {
            const tgt = `${l.screen}_screenshot.jpg`;
            if (src === tgt) continue;
            const edgeId = `edge-${src}-${l.element}-${tgt}`;
            if (!addedEdges.has(edgeId)) { // 检查是否已添加该边缘
                cy.add({ data: { id: edgeId, source: src, target: tgt, label: String(l.element) } });
                addedEdges.add(edgeId); // 将边缘 ID 添加到集合中
                console.log("added edge: " + edgeId);
            }
        }
    }

    if(!nodes.some(n=>n.position)) cy.layout({name:'grid',padding:20}).run();
  }

  async function doRefreshFromBackend(){
    const resp=await fetch(`${API_BASE}/api/refresh`).then(r=>r.json());
    if(!resp.ok) return alert(`刷新失败：${resp.error||'unknown'}`);
    buildGraphFromBackend(resp);
  }

  if(pickBtn){
    pickBtn.addEventListener('click', async ()=>{
      const path=(pathInput?.value||'').trim();
      if(!path) return alert('请输入本地目标文件夹路径');
      const resp=await fetch(`${API_BASE}/api/pick-folder`,{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})
      }).then(r=>r.json());
      if(!resp.ok) return alert(`设置目录失败：${resp.error||'unknown'}`);
      alert(`已设置目录：${resp.path}`);
    });
  }

  if(refreshBtn) refreshBtn.addEventListener('click', doRefreshFromBackend);

  async function saveBatchToBackend(){
    const positions={}; cy.nodes().forEach(n=>positions[n.data('label')]=n.position());
    const payload={ utg, visitList, leafJSON, vhJSON, positions };
    const resp=await fetch(`${API_BASE}/api/save-batch`,{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)
    }).then(r=>r.json());
    if(!resp.ok) return alert(`保存失败：${resp.error||'unknown'}`);
    alert('已保存到后端并更新目标目录');
  }
  if(saveBtn) saveBtn.addEventListener('click', saveBatchToBackend);

  function getSelectedNodeIds(){
    return cy.$('node:selected').map(n=>n.id().replace('_screenshot.jpg',''));
  }

  async function mergeNodesBackend(selectedIds){
    if(!selectedIds || selectedIds.length<2) return alert('至少选择两个节点进行合并（按住 Shift 多选）');
    const keep=selectedIds[0], remove=selectedIds.slice(1);
    const resp=await fetch(`${API_BASE}/api/merge`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ keep, remove, bbox_threshold:BBOX_THRESHOLD })
    }).then(r=>r.json());
    if(!resp.ok) return alert(`后端合并失败：${resp.error||'unknown'}`);
    await doRefreshFromBackend();
    alert('合并完成（后端已更新数据文件）');
  }
  if(mergeBtn) mergeBtn.addEventListener('click', ()=>mergeNodesBackend(getSelectedNodeIds()));

  // 前端连边/删边 + 落盘
  cy.on('tap','node',async (evt)=>{
    const node=evt.target;
    if(evt.originalEvent.shiftKey){ if(node.selected()) node.unselect(); else node.select(); return; }
    const targetNodeId=prompt('Enter the ID of the node to link to:');
    const linkElement=prompt('Enter the ID of the UI element that link the source to the target');
    if(!targetNodeId || !linkElement) return;
    const srcId=node.id();
    const tgtId=targetNodeId.endsWith('_screenshot.jpg')?targetNodeId:`${targetNodeId}_screenshot.jpg`;
    try{
      cy.add({ data:{ id:`edge-${srcId}-${linkElement}-${tgtId}`, source:srcId,target:tgtId,label:String(linkElement) }});
    }catch(e){ console.warn('edge add failed', e); }
    const srcIdx=parseInt(srcId.replace('_screenshot.jpg',''));
    const tgtIdx=parseInt(tgtId.replace('_screenshot.jpg',''));
    if(!isNaN(srcIdx) && !isNaN(tgtIdx)){
      if(!Array.isArray(utg[srcIdx])) utg[srcIdx]=[];
      utg[srcIdx].push({ element: parseInt(linkElement), screen: tgtIdx });
      await saveBatchToBackend();
    }
  });

  document.addEventListener('keydown', async (e)=>{
    if(e.key!=='Delete' && e.key!=='Backspace') return;
    const selectedEdges=cy.$('edge:selected'); if(selectedEdges.length===0) return;
    selectedEdges.forEach(edge=>{
      const src=parseInt(edge.data().source.replace('_screenshot.jpg',''));
      const tgt=parseInt(edge.data().target.replace('_screenshot.jpg',''));
      if(!isNaN(src) && Array.isArray(utg[src])){
        utg[src]=utg[src].filter(link=>parseInt(link.screen)!==tgt);
      }
    });
    selectedEdges.remove();
    await saveBatchToBackend();
  });

  if(downloadBtn){
    downloadBtn.addEventListener('click', ()=>{
      if(typeof JSZip==='undefined' || typeof saveAs==='undefined'){
        return alert('JSZip 或 FileSaver 未加载；请在 index.html 引入相关脚本。');
      }
      const zip=new JSZip();
      zip.file('utg.json', JSON.stringify(utg,null,2));
      zip.file('indexList.json', JSON.stringify(visitList,null,2));
      leafJSON.forEach(it=>{ const d=it?.data||{}; if(d.id?.endsWith('_Leaf.json')) zip.file(d.id, JSON.stringify(d.value||[],null,2)); });
      vhJSON.forEach(it=>{ const d=it?.data||{}; if(d.id?.endsWith('_VH.json')) zip.file(d.id, JSON.stringify(d.value||{},null,2)); });
      zip.generateAsync({type:'blob'}).then(blob=>saveAs(blob,'utg_bundle.zip'));
    });
  }

  // 可选：如果你已经设置过目录，想一进来就刷新，可打开
  // doRefreshFromBackend();
});
