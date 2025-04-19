/**
 * Conversation Flow Editor
 * 
 * This script handles the interactive flow editor for creating and editing
 * conversation flows for campaigns.
 */

// Initialize the flow editor when the DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initFlowEditor();
});

// Global variables
let flowData = {
    nodes: [],
    currentNodeId: null
};
let jsPlumbInstance = null;
let isEditMode = false;
let currentFlowId = null;

/**
 * Initialize the flow editor
 */
function initFlowEditor() {
    // Get the flow ID from the URL if it exists (for editing)
    const urlParams = new URLSearchParams(window.location.search);
    currentFlowId = urlParams.get('flow_id');
    isEditMode = !!currentFlowId;
    
    // Initialize jsPlumb
    jsPlumbInstance = jsPlumb.getInstance({
        Endpoint: ["Dot", { radius: 2 }],
        Connector: ["Bezier", { curviness: 50 }],
        HoverPaintStyle: { stroke: "#1e90ff", strokeWidth: 2 },
        ConnectionOverlays: [
            ["Arrow", { location: 1, width: 10, length: 10, id: "arrow" }]
        ],
        Container: "flow-canvas"
    });
    
    // Set up event listeners
    setupEventListeners();
    
    // If editing an existing flow, load it
    if (isEditMode) {
        loadExistingFlow(currentFlowId);
    } else {
        // Create a new flow with a start node
        createNewFlow();
    }
}

/**
 * Set up event listeners for the flow editor
 */
function setupEventListeners() {
    // Add node button
    document.getElementById('add-node-btn').addEventListener('click', function() {
        showNodeModal('add');
    });
    
    // Save flow button
    document.getElementById('save-flow-btn').addEventListener('click', saveFlow);
    
    // Test flow button
    document.getElementById('test-flow-btn').addEventListener('click', testFlow);
    
    // Node modal save button
    document.getElementById('save-node-btn').addEventListener('click', saveNodeFromModal);
    
    // Node type selection in modal
    document.getElementById('node-type').addEventListener('change', updateNodeModalFields);
    
    // Make nodes draggable
    jsPlumbInstance.draggable(document.querySelectorAll(".flow-node"), {
        grid: [10, 10],
        containment: true,
        stop: function(event) {
            // Update node position in the data model
            const nodeId = event.el.getAttribute('data-node-id');
            const node = findNodeById(nodeId);
            if (node) {
                node.position = {
                    left: parseInt(event.el.style.left, 10),
                    top: parseInt(event.el.style.top, 10)
                };
            }
        }
    });
}

/**
 * Create a new flow with a start node
 */
function createNewFlow() {
    // Create a start node
    const startNode = {
        id: 'start',
        type: 'start',
        text: 'Hello! This is the start of your conversation flow.',
        next: null,
        position: { left: 50, top: 50 }
    };
    
    // Add the start node to the flow
    flowData.nodes.push(startNode);
    flowData.currentNodeId = startNode.id;
    
    // Render the start node
    renderNode(startNode);
}

/**
 * Load an existing flow from the server
 */
function loadExistingFlow(flowId) {
    // Show loading indicator
    document.getElementById('flow-canvas').innerHTML = '<div class="loading">Loading flow...</div>';
    
    // Fetch the flow data from the server
    fetch(`/api/flows/${flowId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load flow');
            }
            return response.json();
        })
        .then(data => {
            // Clear the canvas
            document.getElementById('flow-canvas').innerHTML = '';
            
            // Set the flow data
            flowData = data;
            
            // Render all nodes
            flowData.nodes.forEach(node => {
                renderNode(node);
            });
            
            // Connect the nodes
            connectNodes();
            
            // Set form values
            document.getElementById('flow-name').value = data.name || '';
            document.getElementById('flow-description').value = data.description || '';
            document.getElementById('initial-greeting').value = data.initial_greeting || '';
        })
        .catch(error => {
            console.error('Error loading flow:', error);
            document.getElementById('flow-canvas').innerHTML = 
                `<div class="error">Error loading flow: ${error.message}</div>`;
        });
}

/**
 * Render a node on the canvas
 */
function renderNode(node) {
    // Create the node element
    const nodeEl = document.createElement('div');
    nodeEl.className = `flow-node node-type-${node.type}`;
    nodeEl.setAttribute('data-node-id', node.id);
    nodeEl.setAttribute('data-node-type', node.type);
    
    // Set the node position
    if (node.position) {
        nodeEl.style.left = `${node.position.left}px`;
        nodeEl.style.top = `${node.position.top}px`;
    } else {
        // Default position if none is specified
        nodeEl.style.left = '100px';
        nodeEl.style.top = '100px';
    }
    
    // Set the node content
    let nodeContent = `
        <div class="node-header">${getNodeTypeLabel(node.type)}</div>
        <div class="node-body">${node.text}</div>
        <div class="node-footer">
            <button class="edit-node-btn" data-node-id="${node.id}">Edit</button>
            ${node.type !== 'start' ? `<button class="delete-node-btn" data-node-id="${node.id}">Delete</button>` : ''}
        </div>
    `;
    
    nodeEl.innerHTML = nodeContent;
    
    // Add the node to the canvas
    document.getElementById('flow-canvas').appendChild(nodeEl);
    
    // Make the node draggable
    jsPlumbInstance.draggable(nodeEl, {
        grid: [10, 10],
        containment: true
    });
    
    // Add source and target endpoints based on node type
    if (node.type !== 'end') {
        // Add source endpoint (output)
        jsPlumbInstance.addEndpoint(nodeEl, {
            anchor: "Right",
            isSource: true,
            maxConnections: node.type === 'input' ? -1 : 1,
            connectorStyle: { stroke: "#5c96bc", strokeWidth: 2 }
        });
    }
    
    if (node.type !== 'start') {
        // Add target endpoint (input)
        jsPlumbInstance.addEndpoint(nodeEl, {
            anchor: "Left",
            isTarget: true,
            maxConnections: -1,
            connectorStyle: { stroke: "#5c96bc", strokeWidth: 2 }
        });
    }
    
    // Add event listeners for the node buttons
    nodeEl.querySelector('.edit-node-btn').addEventListener('click', function() {
        const nodeId = this.getAttribute('data-node-id');
        editNode(nodeId);
    });
    
    if (node.type !== 'start') {
        nodeEl.querySelector('.delete-node-btn').addEventListener('click', function() {
            const nodeId = this.getAttribute('data-node-id');
            deleteNode(nodeId);
        });
    }
}

/**
 * Connect nodes based on the flow data
 */
function connectNodes() {
    // Clear existing connections
    jsPlumbInstance.deleteEveryConnection();
    
    // Connect nodes based on 'next' property
    flowData.nodes.forEach(node => {
        if (node.next) {
            // For simple next connections
            if (typeof node.next === 'string') {
                connectTwoNodes(node.id, node.next);
            } 
            // For nodes with options (like input nodes)
            else if (node.options && Array.isArray(node.options)) {
                node.options.forEach(option => {
                    if (option.next) {
                        connectTwoNodes(node.id, option.next, option.value);
                    }
                });
            }
        }
    });
}

/**
 * Connect two nodes with a connection
 */
function connectTwoNodes(sourceId, targetId, label) {
    const sourceEl = document.querySelector(`[data-node-id="${sourceId}"]`);
    const targetEl = document.querySelector(`[data-node-id="${targetId}"]`);
    
    if (!sourceEl || !targetEl) {
        console.error(`Cannot connect nodes: ${sourceId} -> ${targetId}, elements not found`);
        return;
    }
    
    // Create the connection
    const connection = jsPlumbInstance.connect({
        source: sourceEl,
        target: targetEl,
        anchor: ["Right", "Left"],
        connector: ["Bezier", { curviness: 50 }],
        overlays: label ? [
            ["Label", { label: label, location: 0.5, cssClass: "connection-label" }]
        ] : []
    });
    
    return connection;
}

/**
 * Show the node modal for adding or editing a node
 */
function showNodeModal(mode, nodeId) {
    const modal = document.getElementById('node-modal');
    const modalTitle = document.getElementById('node-modal-title');
    
    // Set the modal title based on mode
    modalTitle.textContent = mode === 'add' ? 'Add New Node' : 'Edit Node';
    
    // Clear the form
    document.getElementById('node-form').reset();
    
    // If editing, populate the form with node data
    if (mode === 'edit' && nodeId) {
        const node = findNodeById(nodeId);
        if (node) {
            document.getElementById('node-id').value = node.id;
            document.getElementById('node-type').value = node.type;
            document.getElementById('node-text').value = node.text || '';
            
            // If it's an input node with options, populate the options
            if (node.type === 'input' && node.options) {
                const optionsContainer = document.getElementById('options-container');
                optionsContainer.innerHTML = '';
                
                node.options.forEach((option, index) => {
                    addOptionField(option.value, option.next);
                });
            }
        }
    } else {
        // Generate a new node ID for adding
        document.getElementById('node-id').value = generateNodeId();
    }
    
    // Update the form fields based on the selected node type
    updateNodeModalFields();
    
    // Show the modal
    modal.style.display = 'block';
}

/**
 * Update the node modal fields based on the selected node type
 */
function updateNodeModalFields() {
    const nodeType = document.getElementById('node-type').value;
    const optionsSection = document.getElementById('options-section');
    
    // Show/hide options section based on node type
    if (nodeType === 'input') {
        optionsSection.style.display = 'block';
        
        // If there are no options yet, add two empty ones
        const optionsContainer = document.getElementById('options-container');
        if (optionsContainer.children.length === 0) {
            addOptionField();
            addOptionField();
        }
    } else {
        optionsSection.style.display = 'none';
    }
}

/**
 * Add an option field to the options container
 */
function addOptionField(value = '', next = '') {
    const optionsContainer = document.getElementById('options-container');
    const optionIndex = optionsContainer.children.length;
    
    const optionDiv = document.createElement('div');
    optionDiv.className = 'option-field';
    optionDiv.innerHTML = `
        <div class="form-group">
            <label>Option ${optionIndex + 1}</label>
            <input type="text" class="option-value" value="${value}" placeholder="Option value (e.g., Yes, No)">
            <input type="text" class="option-next" value="${next}" placeholder="Next node ID">
            <button type="button" class="remove-option-btn">Remove</button>
        </div>
    `;
    
    // Add event listener for the remove button
    optionDiv.querySelector('.remove-option-btn').addEventListener('click', function() {
        optionsContainer.removeChild(optionDiv);
        // Renumber the remaining options
        const options = optionsContainer.querySelectorAll('.option-field');
        options.forEach((option, index) => {
            option.querySelector('label').textContent = `Option ${index + 1}`;
        });
    });
    
    optionsContainer.appendChild(optionDiv);
}

/**
 * Save a node from the modal form
 */
function saveNodeFromModal() {
    const nodeId = document.getElementById('node-id').value;
    const nodeType = document.getElementById('node-type').value;
    const nodeText = document.getElementById('node-text').value;
    
    // Create or update the node object
    let node = findNodeById(nodeId);
    const isNewNode = !node;
    
    if (isNewNode) {
        node = {
            id: nodeId,
            type: nodeType,
            text: nodeText,
            position: { left: 200, top: 200 }
        };
        flowData.nodes.push(node);
    } else {
        node.type = nodeType;
        node.text = nodeText;
    }
    
    // Handle node-type specific properties
    if (nodeType === 'input') {
        // Get options from the form
        const optionFields = document.querySelectorAll('.option-field');
        const options = [];
        
        optionFields.forEach(field => {
            const value = field.querySelector('.option-value').value;
            const next = field.querySelector('.option-next').value;
            
            if (value && next) {
                options.push({ value, next });
            }
        });
        
        node.options = options;
    } else {
        // For non-input nodes, just set the next property
        node.next = document.getElementById('node-next').value || null;
    }
    
    // If it's a new node, render it
    if (isNewNode) {
        renderNode(node);
    } else {
        // Update the existing node on the canvas
        updateNodeOnCanvas(node);
    }
    
    // Reconnect all nodes
    connectNodes();
    
    // Close the modal
    document.getElementById('node-modal').style.display = 'none';
}

/**
 * Update a node on the canvas
 */
function updateNodeOnCanvas(node) {
    const nodeEl = document.querySelector(`[data-node-id="${node.id}"]`);
    if (!nodeEl) return;
    
    // Update the node content
    nodeEl.querySelector('.node-header').textContent = getNodeTypeLabel(node.type);
    nodeEl.querySelector('.node-body').textContent = node.text;
    
    // Update the node type class
    nodeEl.className = `flow-node node-type-${node.type}`;
    nodeEl.setAttribute('data-node-type', node.type);
}

/**
 * Edit a node
 */
function editNode(nodeId) {
    showNodeModal('edit', nodeId);
}

/**
 * Delete a node
 */
function deleteNode(nodeId) {
    if (!confirm('Are you sure you want to delete this node?')) {
        return;
    }
    
    // Remove the node from the flow data
    const nodeIndex = flowData.nodes.findIndex(node => node.id === nodeId);
    if (nodeIndex !== -1) {
        flowData.nodes.splice(nodeIndex, 1);
    }
    
    // Remove references to this node from other nodes
    flowData.nodes.forEach(node => {
        if (node.next === nodeId) {
            node.next = null;
        }
        
        if (node.options) {
            node.options.forEach(option => {
                if (option.next === nodeId) {
                    option.next = null;
                }
            });
        }
    });
    
    // Remove the node from the canvas
    const nodeEl = document.querySelector(`[data-node-id="${nodeId}"]`);
    if (nodeEl) {
        jsPlumbInstance.remove(nodeEl);
    }
    
    // Reconnect all nodes
    connectNodes();
}

/**
 * Find a node by its ID
 */
function findNodeById(nodeId) {
    return flowData.nodes.find(node => node.id === nodeId);
}

/**
 * Generate a unique node ID
 */
function generateNodeId() {
    return 'node_' + Math.random().toString(36).substr(2, 9);
}

/**
 * Get a human-readable label for a node type
 */
function getNodeTypeLabel(type) {
    const labels = {
        'start': 'Start',
        'message': 'Message',
        'input': 'Input',
        'condition': 'Condition',
        'end': 'End'
    };
    
    return labels[type] || type;
}

/**
 * Save the flow to the server
 */
function saveFlow() {
    // Get flow metadata from the form
    const flowName = document.getElementById('flow-name').value;
    const flowDescription = document.getElementById('flow-description').value;
    const initialGreeting = document.getElementById('initial-greeting').value;
    
    if (!flowName) {
        alert('Please enter a name for the flow');
        return;
    }
    
    // Prepare the flow data
    const flowToSave = {
        id: currentFlowId,
        name: flowName,
        description: flowDescription,
        initial_greeting: initialGreeting,
        nodes: flowData.nodes,
        start_node_id: 'start'
    };
    
    // Show saving indicator
    const saveBtn = document.getElementById('save-flow-btn');
    const originalText = saveBtn.textContent;
    saveBtn.textContent = 'Saving...';
    saveBtn.disabled = true;
    
    // Determine if we're creating or updating
    const method = isEditMode ? 'PUT' : 'POST';
    const url = isEditMode ? `/api/flows/${currentFlowId}` : '/api/flows';
    
    // Send the data to the server
    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(flowToSave)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to save flow');
        }
        return response.json();
    })
    .then(data => {
        // Update the current flow ID if it's a new flow
        if (!isEditMode) {
            currentFlowId = data.id;
            isEditMode = true;
            
            // Update the URL without reloading the page
            const newUrl = window.location.pathname + '?flow_id=' + currentFlowId;
            window.history.pushState({ flowId: currentFlowId }, '', newUrl);
        }
        
        // Show success message
        alert('Flow saved successfully!');
    })
    .catch(error => {
        console.error('Error saving flow:', error);
        alert('Error saving flow: ' + error.message);
    })
    .finally(() => {
        // Restore the button
        saveBtn.textContent = originalText;
        saveBtn.disabled = false;
    });
}

/**
 * Test the flow in the test interface
 */
function testFlow() {
    if (!currentFlowId) {
        alert('Please save the flow before testing');
        return;
    }
    
    // Redirect to the flow test page
    window.location.href = `/flow_test?flow_id=${currentFlowId}`;
}
