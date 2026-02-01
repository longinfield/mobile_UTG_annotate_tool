document.addEventListener('DOMContentLoaded', function() {
    // ===== NEW: 后端 API 基址 =====
    const API_BASE = 'http://127.0.0.1:5000';

    let cy = cytoscape({
        container: document.getElementById('cy'),
        elements: [],
        style: [
            {
                selector: 'node',
                style: {
                    'background-image': 'data(image)',
                    'background-fit': 'cover',
                    'label': 'data(label)',
                    'shape': 'rectangle',             // Set the default shape to ellipse
                    'width': '270px',                // Set the default width
                    'height': '570px',               // Set the default height
                    'label': 'data(label)',
                    'text-outline-color': '#fff'
                    
                }
            },
            {
                selector: 'node:selected',
                style: {
                    'border-width': '3px',
                    'border-color': 'blue'
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': '#ccc',
                    'target-arrow-color': '#ccc',
                    'target-arrow-shape': 'triangle',
                    'label': 'data(label)',
                    'text-rotation': 'autorotate',
                    'text-margin-y': -10,
                    'font-size': '12px',
                    'color': '#333',
                    'curve-style': 'bezier',
                    //'control-point-distance': 'data(distance)',
                    'control-point-weight': '0.5',
                    'control-point-step-size': 40
                }
            },
            {
                selector: 'edge:selected',
                style: {
                   'line-color': 'blue',
                   'width': 4,
                   'target-arrow-color': 'blue'
                }
            }
        ],
        layout: {
            name: 'grid',
            edgeBendSpacingFactor: 0.8,
            rows: 1
        }
    });

    var visitList;
    var utg;
    var imageNum = 0;
    var leafJSON = [];
    var vhJSON = [];
    // Define a threshold for how close two bounding boxes should be to be considered similar.
    const BBOX_THRESHOLD = 10; // adjust as needed

    //save the node's position so that users do not need to tune it again after refreshing
    async function savePositionsToBackend() {
        const positions = {};
        cy.nodes().forEach(n => {
            positions[n.data('label')] = n.position();
        });
        try {
            await fetch(`${API_BASE}/api/save-positions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ positions })
            });
        } catch (e) {
            console.error('save-positions failed', e);
        }
    }

    // save the node position every 400 ms
    let posSaveTimer = null;
        cy.on('position', 'node', () => {
        if (posSaveTimer) clearTimeout(posSaveTimer);
        posSaveTimer = setTimeout(savePositionsToBackend, 400);
    });

    // ===== NEW: 根据后端 refresh 数据构建图 =====
    //待解决:如果有一部份节点有position，有一部份没有，会怎么样？
    function buildGraphFromBackend(data) {
        cy.elements().remove();
        // leafJSON / vhJSON / visitList / utg 放到全局
        leafJSON = data.leafJSON || [];
        vhJSON = data.vhJSON || [];
        visitList= data.visitList || [];
        utg = data.utg || [];

        // 节点：使用后端提供的 imageUrl 和 position
        const nodes = (data.nodes || []).map(n => ({
            data: { id: n.id, label: n.label, image: n.imageUrl },
            // 如果有历史位置，直接用；否则 Cytoscape 会按当前 layout 放置
            ...(n.position ? { position: n.position, locked: false } : {})
        }));

        cy.add(nodes);

        // 边：遍历 utg
        //utg example: [[{"element": -1,"screen": 0},{"element": 0,"screen": 0}],[{"element": -1,"screen": 0}]]
        for (let i = 0; i < utg.length; i++) {
            const links = utg[i] || [];
            for (let j = 0; j < links.length; j++) {
                const src = `${i}_screenshot.jpg`;
                const tgt = `${links[j].screen}_screenshot.jpg`;
                if (src !== tgt) {
                    try {
                        cy.add({
                            data: {
                                id: `edge-${src}-${links[j].element}-${tgt}`,
                                source: src, target: tgt, label: String(links[j].element)
                            }
                        });
                    } catch(e) {
                        console.warn('edge add failed', e);
                    }
                }
            }
        }

        // 如果后端大多节点已有 position，我们就不强制 layout；否则仍可跑一次 grid
        const hasPositions = nodes.some(n => !!n.position);
        if (!hasPositions) cy.layout({ name: 'grid' }).run();
    }

    // ===== NEW: 选择目标目录（把输入框路径提交到后端） =====
    document.getElementById('pick-folder').addEventListener('click', async () => {
        const path = (document.getElementById('folder-path').value || '').trim();
        if (!path) {
            alert('请输入本地目标文件夹路径');
            return;
        }
        const resp = await fetch(`${API_BASE}/api/pick-folder`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        }).then(r => r.json());
        if (!resp.ok) {
            alert(`设置目录失败：${resp.error || 'unknown'}`);
            return;
        }
        alert(`已设置目录：${resp.path}`);
    });

    // ===== NEW: 刷新（从后端读取并构图） =====
    document.getElementById('refresh-btn').addEventListener('click', async () => {
        const resp = await fetch(`${API_BASE}/api/refresh`).then(r => r.json());
        if (!resp.ok) {
            alert(`刷新失败：${resp.error || 'unknown'}`);
            return;
        }
        buildGraphFromBackend(resp);
        // 更新 imageNum（用于某些已有逻辑）
        imageNum = (resp.nodes || []).length;
    });

    // ======= 你现有的“合并节点”逻辑保留 =======
    // （这里不改你的合并算法，只在合并完成后调用 saveBatchToBackend 持久化）
    // === Merge 辅助：bbox 相似判断（原样保留） ===

    // Helper to determine if two boxes are near each other
    function isBoxSimilar(elem1, elem2) {
      // Check if text is the same and the coordinates are within a small range
      if (elem1.text !== elem2.text) return false;
      const deltaX = Math.abs(elem1['boundLeft'] - elem2['boundLeft']);
      const deltaY = Math.abs(elem1['boundTop'] - elem2['boundTop']);
      const deltaXR = Math.abs((elem1['boundRight']) - (elem2['boundRight']));
      const deltaYB = Math.abs((elem1['boundBottom']) - (elem2['boundBottom']));
      return (deltaX < BBOX_THRESHOLD && deltaY < BBOX_THRESHOLD && deltaXR < BBOX_THRESHOLD && deltaYB < BBOX_THRESHOLD);
    }

    /**
     * Merge the leaf JSON objects from multiple nodes.
     *
     * In addition to returning the merged elements array, this function builds a mapping for each node.
     * mapping[nodeId] is an object that maps the original element index to the new merged index.
     */
    function mergeLeafJSON(leafJSONList, nodeIds) {
      let mergedElements = [];
      let mapping = {}; // mapping[nodeId] = { originalIndex: newMergedIndex, ... }

      // Initialize mapping for each node
      nodeIds.forEach(id => mapping[id] = {});

      // For each leaf JSON object (which comes with an associated nodeId),
      // go through each element and add it to mergedElements if no similar element exists.
      leafJSONList.forEach(({nodeId, leafData}) => {
        leafData.forEach((elem, origIndex) => {
          // Look for a similar element in mergedElements.
          let foundIndex = mergedElements.findIndex(existing => isBoxSimilar(existing, elem));
          if (foundIndex === -1) {
            // Not found: add this element.
            mergedElements.push(elem);
            foundIndex = mergedElements.length - 1;
          }
          // Save the mapping from this node's original element index to the merged element index.
          mapping[nodeId][origIndex] = foundIndex;
        });
      });
      return { mergedElements, mapping };
    }

    /**
     * Merge selected nodes.
     *
     * - The original leaf JSON objects are kept but updated: their id is changed to <nodeid>_Leaf_disabled.json.
     * - A new merged node is created with new leaf JSON, UTG entry, and visited value.
     * - UTG entries in other nodes that refer to one of the merged nodes are updated.
     */
    function mergeNodes(selectedNodeIds) {
      // ……（此处基本保留你的原函数体，唯一新增：合并完成后调用 saveBatchToBackend）……
      console.log(selectedNodeIds);

      // Randomly choose one node id from the selected node ids and convert it to a number.
      let randomIndex = Math.floor(Math.random() * selectedNodeIds.length);
      let chosenNodeId = Number(selectedNodeIds[randomIndex]);
      let newVH = vhJSON[chosenNodeId];
      vhJSON.push(newVH);

      // Build lists for the merging process.
      let leafJSONToMerge = []; // each item: { nodeId, leafData }
      let selectedImages = [];
      let newMergedUTG = [];  // will be the new UTG array for the merged node
      let mergedVisitValues = []; // collect visitList values

      // For each selected node id (remember, these are the cleaned ids without suffix)
      selectedNodeIds.forEach(nodeId => {
        const originalNodeId = nodeId + '_screenshot.jpg';
        const leafId = nodeId + '_Leaf.json';

        // Find the corresponding leaf JSON object.
        let leafObj = leafJSON.find(item => item.data.id === leafId);
        if (leafObj) {
          // Instead of removing, update its id to mark it as disabled.
          leafObj.data.id = nodeId + '_Leaf_disabled.json';
          // Collect its leaf JSON "value" (assumed to be an array of UI elements)
          leafJSONToMerge.push({ nodeId, leafData: leafObj.data.value });//这句似乎有问题
          //leafJSONToMerge.push({ nodeId, leafObj.data.value });
        }

        // Retrieve the image from the node.
        let nodeElement = cy.getElementById(originalNodeId);
        if (nodeElement && nodeElement.data('image')) {
          selectedImages.push(nodeElement.data('image'));
        }

        // Collect its UTG entry.
        // We assume utg is an array where the node index (or id) corresponds to the node.
        // For simplicity, here we assume nodeId (as string) can be parsed as an index.
        let idx = parseInt(nodeId);
        if (!isNaN(idx) && utg[idx]) {
          utg[idx].forEach(record => {
            newMergedUTG.push({ origin: nodeId, record: { ...record } });
          });
          //mergedNodeUTG = mergedNodeUTG.concat(utg[idx]);
        }

        // Collect its visited count from visitList.
        let visitVal = parseInt(visitList[nodeId]);
        if (!isNaN(visitVal)) {
          mergedVisitValues.push(visitVal);
        }

        // Remove the node from Cytoscape.
        let node = cy.getElementById(originalNodeId);
        if (node) {
          cy.remove(node);
        }
      });

      // Merge the leaf JSON elements and obtain a mapping.
      // mapping is an object: mapping[nodeId][originalElementIndex] = newMergedIndex
      let { mergedElements, mapping } = mergeLeafJSON(leafJSONToMerge, selectedNodeIds);

      // Now update the UTG entries for the merged node.
      // For each UTG record from the merged nodes, update the "element" field.

      newMergedUTG = newMergedUTG.map(item => {
        //console.log(item);
        let origNode = item.origin;
        if (mapping[origNode] && typeof item.record.element === 'number' && item.record.element!==-1) {
            //console.log(mapping);
            //console.log(mapping[origNode]);
            //console.log(item.record.element);
            //console.log(item.record.element);
            if (selectedNodeIds.includes(item.record.screen.toString())) {
                item.record.screen = visitList.length;
            }else{
                item.record.element = mapping[origNode][item.record.element];
            }
        }else if (item.record.element===-1){
            item.record.screen = visitList.length;
        }
        return item.record;
      });

      // Remove duplicate UTG records (duplicates have identical 'element' and 'screen' fields)
      newMergedUTG = newMergedUTG.filter((record, index, self) =>
        index === self.findIndex(t => t.element === record.element && t.screen === record.screen)
      );

      // Also, for UTG records in nodes that are not merged,
      // if their "screen" field points to one of the selected nodes,
      // update that screen field to the new merged node index.
      // Here, we loop over all utg entries.
      var changedUTG = [];
      for (let i = 0; i < utg.length; i++) {
        console.log(utg[i]);
        if(utg[i][utg[i].length - 1].element === 'disabled'){
          continue;
        }
        utg[i] = utg[i].map(link => {
          //console.log(link);
          //console.log(selectedNodeIds);
          //console.log(link.screen.toString());
          if (selectedNodeIds.includes(link.screen.toString())) {
            //console.log('true');
            // Update screen field to new node id (as string)
            link.screen = visitList.length;
            changedUTG.push({oriScreen: i, element: link.element, screen: visitList.length});
          }

          return link;
        });
        console.log(utg[i]);
      }

      // Determine the new node's id.
      let newNodeIndex = visitList.length;
      let newNodeId = newNodeIndex.toString();

      // Randomly select an image from the selected images.
      let newImage = 'default.jpg'; // fallback
      if (selectedImages.length > 0) {
        let randomIndex = Math.floor(Math.random() * selectedImages.length);
        newImage = selectedImages[randomIndex];

      }

      // Add the new merged node to Cytoscape.
      cy.add({
        data: {
          id: newNodeId+'_screenshot.jpg',
          label: newNodeId+'_screenshot.jpg',
          image: newImage
        }
      });
      //cy.layout({ name: 'grid' }).run();

      // Add the new merged leaf JSON to the global array.
      leafJSON.push({
        data: {
          id: newNodeId + '_Leaf.json',
          value: mergedElements
        }
      });

      // Update visitedList: choose the max value among the merged nodes.
      let newVisit = mergedVisitValues.length ? Math.max(...mergedVisitValues) : 0;
      visitList.push(newVisit);

      // Append the new UTG entry for the merged node.
      // (Assuming that utg is an array indexed by node id.)
      //utg[newNodeIndex] = newMergedUTG;
      utg.push(newMergedUTG);

      // --- Build edges where the new merged node is the source ---
      // For each UTG record in newMergedUTG, create an edge from new node (source) to record.screen (target).
      newMergedUTG.forEach(record => {
          cy.add({
            data: {
              id: 'edge-' + newNodeId+'_screenshot.jpg' + '-' + record.element.toString() + '-' + record.screen.toString()+'_screenshot.jpg',
              source: newNodeId+'_screenshot.jpg',
              target: record.screen.toString()+'_screenshot.jpg',
              label: record.element.toString() // or adjust the label as needed
            }
          });
      });

      // --- Build edges where the new merged node is the target ---
      // Scan through the global utg array to find links that now reference the new merged node as screen.
      /*
      for (let i = 0; i < utg.length-1; i++) {
          if (selectedNodeIds.includes(i.toString())){
            utg[i].push({element:'disabled'});
            continue;
          }
          utg[i].forEach(link => {
            // If a UTG record from node i now targets the new merged node,
            // then add an edge from node i (source) to the new merged node (target).
            if (link.screen === newNodeId) {
              console.log(utg[i]);
              // Create an edge. The id is composed using the source, target and element.
              cy.add({
                data: {
                  id: 'edge-' + i.toString()+'_screenshot.jpg' + '-' + link.element.toString() + '-' + newNodeId+'_screenshot.jpg',
                  source: i.toString()+'_screenshot.jpg',
                  target: newNodeId+'_screenshot.jpg',
                  label: link.element.toString() // Adjust as needed
                }
              });
            }
          });
      }*/
      for (let i = 0; i < utg.length-1; i++) {
          if (selectedNodeIds.includes(i.toString())){
            utg[i].push({element:'disabled'});
            //continue;
          }
      }
      console.log(changedUTG);
      for (let i = 0; i < changedUTG.length; i++){
          console.log(changedUTG[i]);
          if (!selectedNodeIds.includes(changedUTG[i].oriScreen.toString())){
            console.log('draw');
            try {
                cy.add({
                data: {
                  id: 'edge-' + changedUTG[i].oriScreen.toString()+'_screenshot.jpg' + '-' + changedUTG[i].element.toString() + '-' + newNodeId+'_screenshot.jpg',
                  source: changedUTG[i].oriScreen.toString()+'_screenshot.jpg',
                  target: newNodeId+'_screenshot.jpg',
                  label: changedUTG[i].element.toString() // Adjust as needed
                }
            });
            } catch(error){
                console.error('Error occurred during loop execution:', error);
            }
          }
      }

      // Finally, run a layout update.
      cy.layout({ name: 'grid' }).run();

      // (Optional) Log the updated data for debugging.
      console.log("Merged leaf elements:", mergedElements);
      console.log("New UTG entry:", newMergedUTG);
      console.log("Updated visitList:", visitList);
      console.log("Updated utg:", utg);
      console.log("Updated vhJSON:", vhJSON);

      // === ！！重要：合并完成后，调用持久化 ===
      saveBatchToBackend();
    }

    document.getElementById('merge-nodes-btn').addEventListener('click', function() {
        let selectedNodeIds = getSelectedNodeIds();
      if (selectedNodeIds.length < 2) {
        alert("Select at least two nodes to merge (shift-click on nodes to select them).");
        return;
      }
        mergeNodes(selectedNodeIds);
    });

    // ===== NEW: 批量保存当前状态到后端（按钮 & 自动调用） =====
    async function saveBatchToBackend() {
        try {
            // 同步最新 positions
            const positions = {};
            cy.nodes().forEach(n => {
                positions[n.data('label')] = n.position();
            });

            // 准备 payload（与你的 universalDownloadZip 类似，但只是发到后端）
            const payload = {
                utg, visitList, leafJSON, vhJSON, positions
            };
            const resp = await fetch(`${API_BASE}/api/save-batch`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(r => r.json());
            if (!resp.ok) {
                alert(`保存失败：${resp.error || 'unknown'}`);
                return;
            }
            alert('已保存到后端并更新目标目录');
        } catch (e) {
            console.error(e);
            alert('保存失败，请查看控制台错误');
        }
    }
    document.getElementById('save-batch-btn').addEventListener('click', saveBatchToBackend);

    // In your JavaScript, after defining universalDownload():
    document.getElementById('download-btn').addEventListener('click', function() {
        universalDownloadZip();
    });

    // 你原有的 universalDownloadZip、processUTGData 等函数如果还需要，也可保留
    // ……（从你的原文件复制过来，保持一致）……
    // Helper: Download a JSON object as a file (if needed outside zip, not used here).
    function downloadJSON(data, filename) {
      const jsonStr = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    }

    // Universal function to download all JSON and image files as a ZIP.
    function universalDownloadZip() {
      // Deep copy the current global data to avoid modifying the front-end state.
      const utgCopy = JSON.parse(JSON.stringify(utg));
      const visitListCopy = JSON.parse(JSON.stringify(visitList));
      const leafJSONCopy = JSON.parse(JSON.stringify(leafJSON));

      // Build a mapping from original UTG index to new index.
      const mapping = {}; // { originalIndex: newIndex }
      const filteredUTG = [];
      const filteredVisitList = [];

      for (let i = 0; i < utgCopy.length; i++) {
        const subArray = utgCopy[i];
        // Skip this UTG sub-array if its last element is { element: 'disabled' }.
        if (subArray.length > 0 && subArray[subArray.length - 1].element === 'disabled') {
          continue;
        }
        mapping[i] = filteredUTG.length;
        filteredUTG.push(subArray);
        filteredVisitList.push(visitListCopy[i]);
      }

      // **Update UTG sub-array "screen" values to reflect new mapping**
      filteredUTG.forEach(utgSubArray => {
        utgSubArray.forEach(record => {
          if (mapping.hasOwnProperty(record.screen)) {
            record.screen = mapping[record.screen]; // Update the screen value
          }
        });
      });

      // Process the leafJSON copy: remove disabled objects and update IDs.
      // Also store the original index for screenshot lookup.
      const updatedLeafJSON = [];
      leafJSONCopy.forEach(leafObj => {
        // Expect id like "15_Leaf.json" or "15_Leaf_disabled.json".
        if (leafObj.data.id.indexOf("disabled") !== -1) {
          return; // Skip disabled leaf JSON.
        }
        const parts = leafObj.data.id.split('_');
        const origIndex = parseInt(parts[0], 10);
        if (mapping.hasOwnProperty(origIndex)) {
          const newIndex = mapping[origIndex];
          // Update the leafJSON id to reflect its new position.
          leafObj.data.id = newIndex + '_Leaf.json';
          // Store the original index for later screenshot lookup.
          leafObj.data.originalIndex = origIndex;
          updatedLeafJSON.push(leafObj);
        }
      });

      // Create a new ZIP archive.
      const zip = new JSZip();

      // Add the filtered UTG and visitList JSON files.
      zip.file("updated_utg.json", JSON.stringify(filteredUTG, null, 2));
      zip.file("updated_visitList.json", JSON.stringify(filteredVisitList, null, 2));

      // Add each updated leaf JSON as its own file,
      // and add its corresponding screenshot image.
      updatedLeafJSON.forEach(leafObj => {
        // Use the updated leaf JSON id as the filename.
        zip.file(leafObj.data.id, JSON.stringify(leafObj.data.value, null, 2));

        // The new index is extracted from the updated id.
        const newIndex = leafObj.data.id.split('_')[0];
        // Retrieve the original index from the stored property.
        const origIndex = leafObj.data.originalIndex;

        zip.file(newIndex+'_VH.json', JSON.stringify(vhJSON[Number(origIndex)].data.value, null, 2));

        // Look up the screenshot node using the original index.
        // (Assumes node id is formatted as "<originalIndex>_screenshot.jpg")
        const node = cy.getElementById(origIndex + "_screenshot.jpg");
        if (node && node.data('image')) {
          // The node's image should be a data URL.
          const dataURL = node.data('image');
          // Remove the prefix ("data:image/png;base64,") and add the image file using the new index.
          const base64Data = dataURL.split(',')[1];
          zip.file(newIndex + "_screenshot.jpg", base64Data, { base64: true });
        }
      });

      // Generate the ZIP file as a Blob and trigger its download.
      zip.generateAsync({ type: "blob" }).then(function(content) {
        saveAs(content, "download.zip");
      });
    }

    // 处理UTG数据
    function processUTGData(utgData,len) {
        utg = utgData;
        console.log(utg.length);
        let sourceID, targetID;
        if (len===utg.length){
            for (let i = 0; i<utg.length;i++){
                console.log(utg[i]);
                if (utg[i][utg[i].length-1].element === 'disabled'){
                    continue;
                }
                for (let j = 0; j<utg[i].length;j++){
                    console.log(utg[i][j]);
                    sourceID = i.toString()+ '_screenshot.jpg'
                    targetID = utg[i][j]['screen'].toString()+'_screenshot.jpg'


                    if (sourceID!==targetID){
                        try {
                            cy.add({
                                data: {
                                    id: 'edge-' + sourceID + '-'+ utg[i][j]['element'].toString()+'-' + targetID,
                                    source: sourceID,
                                    target: targetID,
                                    label: utg[i][j]['element'].toString()
                                }
                            });
                        } catch (error) {
                            console.error(error);
                            utg[i].splice(j,1);

                            /*let candidateID = cy.$id('edge-' + sourceID + '-'+ utg[i][j]['element'].toString()+'-' + targetID);
                            console.error(candidateID);
                            if(candidateID.length>0){
                                cy.add({
                                    data: {
                                        id: candidateID.id()+"p",
                                        source: sourceID,
                                        target: targetID,
                                        label: utg[i][j]['element'].toString()
                                    }
                                });
                            }*/
                        }
                    }
                }
            }

        }
    }

    // ====== 你原有的“手动添加/删除边”“弹窗BBX”等逻辑保持 ======
    // 重要改动：在“添加边”与“删除边”结束后，同步调用 saveBatchToBackend() 持久化
    cy.on('tap', 'node', function(event) {
        const node = event.target;
        if (event.originalEvent.shiftKey) {
            // If shift is held, toggle selection instead of prompting for linking.
            if (node.selected()) {
                node.unselect();
                // Optionally, you can change the style or add a class to show unselection.
            } else {
                node.select();
                // Optionally, you can change the style or add a class to show selection.
            }
        } else {
            // Normal tap: prompt for linking nodes.
            console.log(utg);
            const targetNodeId = prompt("Enter the ID of the node to link to:");
            const linkElement = prompt("Enter the ID of the UI element that link the source to the target");
            if (targetNodeId) {
                cy.add({
                    data: {
                        id: 'edge-' + node.id() + '-'+ linkElement+'-' + targetNodeId,
                        source: node.id(),
                        target: targetNodeId,
                        label: linkElement,
                    }
                });
            }

            // Update UTG data.
            // Assume node ids are like "15_screenshot.jpg"; extract numeric part.
            let srcNum = parseInt(node.id().replace('_screenshot.jpg', ''));
            let tgtNum = parseInt(targetNodeId.replace('_screenshot.jpg', ''));
            if (!utg[srcNum]) utg[srcNum] = [];
            utg[srcNum].push({ element: parseInt(linkElement), screen: tgtNum });
            console.log(utg);

            // Log all edge IDs for debugging.
            cy.edges().forEach(edge => {
                console.log(edge.id());
            });
            // NEW: 增量操作后持久化
            saveBatchToBackend();
        }
    });

    // Listen for tap on an edge to toggle its selection.
    cy.on('tap', 'edge', function(event) {
      let edge = event.target;
      // Toggle selection state.
      if (edge.selected()) {
        edge.unselect();
      } else {
        edge.select();
      }
    });

    // Listen for keydown events on the document.
    document.addEventListener('keydown', function(e) {
      // Check if the pressed key is Delete or Backspace.
      if (e.key === 'Delete' || e.key === 'Backspace') {
        // Remove all selected edges.
        let selectedEdges = cy.$('edge:selected');
        // Optionally update UTG data for each removed edge.
        selectedEdges.forEach(edge => {
          // For example, remove UTG links corresponding to this edge.
          // Assume edge.data().source and edge.data().target are node IDs.
          // You may need to convert these IDs (e.g. strip suffix) to match your UTG indices.
          let src = parseInt(edge.data().source.replace('_screenshot.jpg', ''));
          let tgt = parseInt(edge.data().target.replace('_screenshot.jpg', ''));
          // Find and remove the UTG link from utg[src] with screen == tgt and matching element if needed.
          if (utg[src]) {
            utg[src] = utg[src].filter(link => link.screen !== tgt);
          }
        });
        selectedEdges.remove();
      }
      // NEW: 删除后持久化
      saveBatchToBackend();
    });


    function getSelectedNodeIds() {
        return cy.$('node:selected').map(node => {
        let id = node.id();
        // Remove the "_screenshot.jpg" suffix if present.
        if (id.endsWith('_screenshot.jpg')) {
          id = id.replace('_screenshot.jpg', '');
        }
        return id;
        });
    }

    var node_index;

    cy.on('cxttap', 'node', function(evt) {
        var node = evt.target;
        var imageUrl = node.data('image');
        var node_label = node.data('label');
        node_index = node_label.split('_')[0];
        var popup = document.getElementById('popup');
        var popupImage = document.getElementById('popup-image');

        var drawingCanvas = document.getElementById('drawing-canvas');
        var ctx = drawingCanvas.getContext('2d');

        // Get the position of the node
        var nodePosition = node.renderedPosition();
        var cyContainer = cy.container();

        // Set the position of the pop-up
        popup.style.left = (nodePosition.x + cyContainer.offsetLeft) + 'px';
        popup.style.top = (nodePosition.y + cyContainer.offsetTop) + 'px';

        popupImage.src = imageUrl;
        popup.style.display = 'block';

        // Set canvas size to match image
        popupImage.onload = function() {
            drawingCanvas.width = popupImage.clientWidth;
            drawingCanvas.height = popupImage.clientHeight;
            ctx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
        };
    });

    cy.on('cxttap', 'edge', function(evt) {
        var edge = evt.target;
        var edgePopup = document.getElementById('edge-popup');
        var edgeInfo = document.getElementById('edge-info');
        var edgeSourceImage = document.getElementById('edge-source-image');

        // Get the source node of the edge
        var sourceNode = edge.source();
        var source_index = sourceNode.data('label').split('_')[0];
        var sourceImageUrl = sourceNode.data('image');

        // Get the target node of the edge
        var targetNode = edge.target();
        var target_index = targetNode.data('label').split('_')[0];

        //var drawingEdgeNodeCanvas = document.getElementById('drawing-canvas');
        //var ctx = drawingEdgeNodeCanvas.getContext('2d');
        var ctx = drawingEdgeNodeCanvas.getContext('2d')
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        

        // Set canvas size to match image
        /*
        edgeSourceImage.onload = function() {
            drawingEdgeNodeCanvas.width = edgeSourceImage.clientWidth;
            drawingEdgeNodeCanvas.height = edgeSourceImage.clientHeight;
            ctx.clearRect(0, 0, drawingEdgeNodeCanvas.width, drawingEdgeNodeCanvas.height);
        };*/

        // Get the position of the edge
        var edgePosition = evt.renderedPosition || { x: evt.cyPosition.x, y: evt.cyPosition.y };
        var cyContainer = cy.container();

        // Set the position of the pop-up
        edgePopup.style.left = (edgePosition.x + cyContainer.offsetLeft) + 'px';
        edgePopup.style.top = (edgePosition.y + cyContainer.offsetTop) + 'px';

        edgeInfo.innerHTML = `Edge from ${edge.data('source')} to ${edge.data('target')}`;
        edgeSourceImage.src = sourceImageUrl;

        /*
        // Fetch the JSON data from the URL
        fetch('com.openrice.android/'+source_index+'_Leaf.json')
        //fetch('ctrip.english/'+source_index+'_Leaf.json')
        .then((response) => {
            // Check if the response status is OK (200)
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            // Parse the JSON data from the response body
            return response.json();
        })
        .then((jsonData) => {*/
        let leaf;
        for (let k = 0; k<leafJSON.length; k++){
            leaf = leafJSON[k].data;
            if (leaf.id === source_index+'_Leaf.json'){
                break;
            }
        }

        const jsonData = leaf.value;
        console.log(jsonData);
        console.log(utg[Number(source_index)]);
        console.log(target_index);
        // find the edge in utg that link these two nodes
        //let links=[];
        let edges = utg[Number(source_index)];
        for (let i=0;i<edges.length;i++){
            if(edges[i]['screen'] == target_index){
                //links.push()
                let linkUI = jsonData[edges[i]['element']];
                console.log(edges[i]['element']);

                //let flag;
                let x = linkUI['boundLeft']/8;
                let y = linkUI['boundTop']/8;
                let w = linkUI['boundRight']/8-x;
                let h = linkUI['boundBottom']/8-y;

                if(x>=0 && y>=0 && w>0 && h>0){
                    drawRect(drawingEdgeNodeCanvas.getContext('2d'), x, y, w, h, edges[i]['element'], 0);
                }
            }
        }
            
        //})
        edgePopup.style.display = 'block';
    });

    document.getElementById('popup-close').addEventListener('click', function() {
        var popup = document.getElementById('popup');
        popup.style.display = 'none';
    });

    document.getElementById('edit-popup-close').addEventListener('click', function() {
        var editPopup = document.getElementById('edit-popup');
        editPopup.style.display = 'none';
    });

    document.getElementById('edge-popup-close').addEventListener('click', function() {
        var edgePopup = document.getElementById('edge-popup');
        edgePopup.style.display = 'none';
    });

    var drawing = false;
    var startX, startY;
    var rectangles = [];
    var selectedRectangleIndex = null;

    function getRectangleAt(x, y) {
        return rectangles.findIndex(rect => x >= rect.left/8 && x <= (rect.left + rect.width)/8 && y >= rect.top/8 && y <= (rect.top + rect.height)/8);
    }

    function drawRect(ctx, x, y, w, h,number,flag) {
        //ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        console.log([x, y, w, h]);
        if(flag===1){
            ctx.fillStyle = 'rgba(76, 175, 80, 0.5)';
            ctx.fillRect(x, y, w, h);
        }else{
            ctx.fillStyle = 'rgba(175, 76, 80, 0.5)';
            ctx.fillRect(x, y, w, h);
        }
        ctx.fillStyle = 'black';
        ctx.font = '12px Arial';
        ctx.fillText(number.toString(), x + 5, y + 5);
    }

    // canvas and bbx on edge source node images
    var drawingEdgeNodeCanvas = document.getElementById('source-drawing-canvas');
    drawingEdgeNodeCanvas.addEventListener('mousedown', function(e) {
        var rect = drawingEdgeNodeCanvas.getBoundingClientRect();
        var mouseX = e.clientX - rect.left;
        var mouseY = e.clientY - rect.top;

        drawing = true;
        startX = mouseX;
        startY = mouseY;
    });

    drawingEdgeNodeCanvas.addEventListener('mousemove', function(e) {
        if (!drawing) return;
        var ctx = drawingEdgeNodeCanvas.getContext('2d');
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        var rect = drawingEdgeNodeCanvas.getBoundingClientRect();
        var mouseX = e.clientX - rect.left;
        var mouseY = e.clientY - rect.top;
        var width = mouseX - startX;
        var height = mouseY - startY;
        drawRect(ctx, startX,startY,width,height,-1,0);
    });

    drawingEdgeNodeCanvas.addEventListener('mouseup', function() {
        if (!drawing) return;
        var ctx = drawingEdgeNodeCanvas.getContext('2d');
        rectangles = [];
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        var rect = drawingEdgeNodeCanvas.getBoundingClientRect();
        var mouseX = event.clientX - rect.left;
        var mouseY = event.clientY - rect.top;
        var width = mouseX - startX;
        var height = mouseY - startY;
        drawRect(ctx,startX,startY,width,height,-1,0);
        console.log(rectangles);
        drawing = false;
    });

    drawingEdgeNodeCanvas.addEventListener('mouseout', function() {
        drawing = false;
    });


    // canvas and bbx on node images
    var drawingCanvas = document.getElementById('drawing-canvas');
    drawingCanvas.addEventListener('mousedown', function(e) {
        var rect = drawingCanvas.getBoundingClientRect();
        var mouseX = e.clientX - rect.left;
        var mouseY = e.clientY - rect.top;
        selectedRectangleIndex = getRectangleAt(mouseX, mouseY);

        if (selectedRectangleIndex >= 0) {
            // Open edit popup for selected rectangle 
            var editPopup = document.getElementById('edit-popup');
            var selectedRectangle = rectangles[selectedRectangleIndex];

            document.getElementById('edit-text').value = selectedRectangle.text;
            document.getElementById('edit-x').value = selectedRectangle.left;
            document.getElementById('edit-y').value = selectedRectangle.top;
            document.getElementById('edit-width').value = selectedRectangle.width;
            document.getElementById('edit-height').value = selectedRectangle.height;

            editPopup.style.left = e.clientX + 'px';
            editPopup.style.top = e.clientY + 'px';
            editPopup.style.display = 'block';
        } else {
            drawing = true;
            startX = mouseX;
            startY = mouseY;
        }
    });

    drawingCanvas.addEventListener('mousemove', function(e) {
        if (!drawing) return;
        var ctx = drawingCanvas.getContext('2d');
        rectangles = [];
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        var rect = drawingCanvas.getBoundingClientRect();
        var mouseX = e.clientX - rect.left;
        var mouseY = e.clientY - rect.top;
        var width = mouseX - startX;
        var height = mouseY - startY;
        var tempRectangles = rectangles.slice();
        tempRectangles.push({ left: startX, top: startY, width: width, height: height, text: 'Rectangle' });
        drawRect(ctx, startX,startY,width,height,-1,0);
    });

    drawingCanvas.addEventListener('mouseup', function() {
        if (!drawing) return;
        var ctx = drawingCanvas.getContext('2d');
        rectangles = [];
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        var rect = drawingCanvas.getBoundingClientRect();
        var mouseX = event.clientX - rect.left;
        var mouseY = event.clientY - rect.top;
        var width = mouseX - startX;
        var height = mouseY - startY;
        rectangles.push({ left: startX*8, top: startY*8, width: width*8, height: height*8, text: 'Rectangle' });
        drawRect(ctx,startX,startY,width,height,-1,0);
        console.log(rectangles);
        drawing = false;
    });

    drawingCanvas.addEventListener('mouseout', function() {
        drawing = false;
    });

    document.getElementById('save-changes').addEventListener('click', function() {
        if (selectedRectangleIndex !== null) {
            var selectedRectangle = rectangles[selectedRectangleIndex];

            selectedRectangle.text = document.getElementById('edit-text').value;
            selectedRectangle.left = parseFloat(document.getElementById('edit-x').value);
            selectedRectangle.top = parseFloat(document.getElementById('edit-y').value);
            selectedRectangle.width = parseFloat(document.getElementById('edit-width').value);
            selectedRectangle.height = parseFloat(document.getElementById('edit-height').value);

            //drawRectangles(drawingCanvas.getContext('2d'));

            var editPopup = document.getElementById('edit-popup');
            editPopup.style.display = 'none';
            selectedRectangleIndex = null;
        }
    });

    document.getElementById('popup-button').addEventListener('click', function() {
        /*
        // Fetch the JSON data from the URL
        fetch('com.openrice.android/'+node_index+'_Leaf.json')
        //fetch('ctrip.english/'+node_index+'_Leaf.json')
        .then((response) => {
            // Check if the response status is OK (200)
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            // Parse the JSON data from the response body
            return response.json();
        })
        .then((jsonData) => {*/
        let leaf;
        for (let k = 0; k<leafJSON.length; k++){
            leaf = leafJSON[k].data;
            if (leaf.id === node_index+'_Leaf.json'){
                break;
            }
        }

        const jsonData = leaf.value;
        console.log(jsonData);
        console.log(utg[Number(node_index)]);

        for (let i = 0; i<jsonData.length;i++){
            console.log(jsonData[i]);
            let flag;
            if(i<=visitList[Number(node_index)]){
                flag = 1;
            }else{
                flag = 0;
            }

            let x = jsonData[i]['boundLeft']/8;
            let y = jsonData[i]['boundTop']/8;
            let w = jsonData[i]['boundRight']/8-x;
            let h = jsonData[i]['boundBottom']/8-y;

            if(x>=0 && y>=0 && w>0 && h>0){
                rectangles.push({ left: jsonData[i]['boundLeft'], top: jsonData[i]['boundTop'], width: jsonData[i]['boundRight']-jsonData[i]['boundLeft'], height: jsonData[i]['boundBottom']-jsonData[i]['boundTop'], number: i.toString(), text: jsonData[i]["text"]
                 });
                drawRect(drawingCanvas.getContext('2d'), x, y, w, h, i, flag);
            }
        }
        //})
    });

    
});
