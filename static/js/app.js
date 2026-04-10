let editor;
var currentFlowId = null;
let executionWs = null;
let selectedNodeId = null;
let pendingHitlNodeId = null;

const nodeTemplates = {
  start: `<div class="df-node-content">
    <div class="df-node-header start">
      <span>▶</span><span>Start</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Entry point</div>
    </div>
  </div>`,

  llm: `<div class="df-node-content">
    <div class="df-node-header llm">
      <span>🤖</span><span>LLM Call</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">AI Model</div>
    </div>
  </div>`,

  prompt_template: `<div class="df-node-content">
    <div class="df-node-header prompt_template">
      <span>📝</span><span>Template</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Prompt Template</div>
    </div>
  </div>`,

  conditional: `<div class="df-node-content">
    <div class="df-node-header conditional">
      <span>🔀</span><span>Condition</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">True / False</div>
    </div>
  </div>`,

  code: `<div class="df-node-content">
    <div class="df-node-header code">
      <span>💻</span><span>Code</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Python</div>
    </div>
  </div>`,

  merge: `<div class="df-node-content">
    <div class="df-node-header merge">
      <span>🔗</span><span>Merge</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Combine inputs</div>
    </div>
  </div>`,

  output: `<div class="df-node-content">
    <div class="df-node-header output">
      <span>📤</span><span>Output</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Result</div>
    </div>
  </div>`,

  shell: `<div class="df-node-content">
    <div class="df-node-header shell">
      <span>⌨</span><span>Shell</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Run command</div>
    </div>
  </div>`,

  http_request: `<div class="df-node-content">
    <div class="df-node-header http_request">
      <span>🌐</span><span>HTTP Request</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">GET</div>
    </div>
  </div>`,

  file_read: `<div class="df-node-content">
    <div class="df-node-header file_read">
      <span>📂</span><span>File Read</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Read file</div>
    </div>
  </div>`,

  file_write: `<div class="df-node-content">
    <div class="df-node-header file_write">
      <span>💾</span><span>File Write</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Write file</div>
    </div>
  </div>`,

  loop: `<div class="df-node-content">
    <div class="df-node-header loop">
      <span>🔁</span><span>Loop</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Iterate until condition</div>
    </div>
  </div>`,

  hitl: `<div class="df-node-content">
    <div class="df-node-header hitl">
      <span>👤</span><span>Human Review</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Approval gate</div>
    </div>
  </div>`,

  react_agent: `<div class="df-node-content">
    <div class="df-node-header react_agent">
      <span>🧠</span><span>ReAct Agent</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Autonomous agent</div>
    </div>
  </div>`,

  conversation_memory: `<div class="df-node-content">
    <div class="df-node-header conversation_memory">
      <span>💬</span><span>Memory</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Conversation state</div>
    </div>
  </div>`,

  map_reduce: `<div class="df-node-content">
    <div class="df-node-header map_reduce">
      <span>⚡</span><span>Map-Reduce</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Parallel processing</div>
    </div>
  </div>`,

  embed: `<div class="df-node-content">
    <div class="df-node-header embed">
      <span>🔢</span><span>Embed</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Text → Vectors</div>
    </div>
  </div>`,

  vector_store: `<div class="df-node-content">
    <div class="df-node-header vector_store">
      <span>🗄️</span><span>Vector Store</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Store & search</div>
    </div>
  </div>`,

  rag_retrieve: `<div class="df-node-content">
    <div class="df-node-header rag_retrieve">
      <span>🎯</span><span>RAG Retrieve</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">Semantic search</div>
    </div>
  </div>`,

  ui_interface: `<div class="df-node-content">
    <div class="df-node-header ui_interface">
      <span>🖥️</span><span>Interface</span>
      <span class="df-node-status idle"></span>
    </div>
    <div class="df-node-body">
      <div class="df-node-info">User-facing UI</div>
    </div>
  </div>`
};

const defaultNodeData = {
  start: { label: 'Start', input_text: '' },
  llm: {
    label: 'LLM Call',
    provider: '',
    model: '',
    system_prompt: 'You are a helpful assistant.',
    user_prompt_template: '{{input}}',
    temperature: 0.7,
    max_tokens: 2048
  },
  prompt_template: { label: 'Template', template: '{{input}}' },
  conditional: { label: 'Condition', condition_type: 'contains', condition_value: '' },
  output: { label: 'Output', output_name: 'result' },
  code: { label: 'Code', code: '# input_data contains incoming text\noutput = input_data', unrestricted: false },
  merge: { label: 'Merge', merge_mode: 'concatenate', separator: '\n\n' },
  shell: { label: 'Shell', command_template: '', shell_type: 'powershell', timeout: 30, working_directory: '' },
  http_request: { label: 'HTTP Request', method: 'GET', url_template: '', headers_json: '', body_template: '', extract_path: '', timeout: 30 },
  file_read: { label: 'File Read', file_path_template: '' },
  file_write: { label: 'File Write', file_path: '', write_mode: 'write' },
  loop: {
    label: 'Loop', loop_mode: 'code', max_iterations: 5,
    condition_type: 'contains', condition_value: '',
    loop_code: '# input_data = current value, iteration = loop index\noutput = input_data',
    loop_delay_ms: 0, unrestricted: false,
    loop_provider: '', loop_model: '', loop_system_prompt: '',
    loop_user_template: '{{input}}', loop_temperature: 0.7, loop_max_tokens: 1024,
    loop_command: '', loop_shell_type: 'powershell'
  },
  hitl: {
    label: 'Human Review', prompt_message: 'Review and approve this data:',
    allow_edit: true, timeout: 300
  },
  react_agent: {
    label: 'ReAct Agent', goal: '', provider: '', model: '',
    system_prompt: '', temperature: 0.3, max_tokens: 2048,
    max_iterations: 10, allowed_tools: 'shell,code,http,file_read,file_write'
  },
  conversation_memory: {
    label: 'Memory', memory_id: '', strategy: 'full',
    max_messages: 50, role: 'user', output_format: 'json',
    persist_path: ''
  },
  map_reduce: {
    label: 'Map-Reduce', split_mode: 'newline', reduce_mode: 'concatenate',
    separator: '\n', max_parallel: 5,
    map_node_type: 'code', map_node_data: { code: 'output = input_data.upper()' },
    reduce_code: "output = '\\n'.join(items)"
  },
  embed: {
    label: 'Embed', collection: 'default', operation: 'embed_and_store',
    chunk_size: 0, chunk_overlap: 50, metadata_json: ''
  },
  vector_store: {
    label: 'Vector Store', collection: 'default', operation: 'query',
    top_k: 5, threshold: 0.0, metadata_json: ''
  },
  rag_retrieve: {
    label: 'RAG Retrieve', collection: 'default', top_k: 5,
    threshold: 0.3, output_format: 'context'
  },
  ui_interface: {
    label: 'Interface', mode: 'chat', title: 'My App',
    description: 'Interact with this flow', theme: 'dark',
    chat_history_path: '', output_node_key: '',
    show_thinking: false, accent_color: '#6366f1',
    fields: [],
    output_fields: []
  }
};

const nodeIO = {
  start: { inputs: 0, outputs: 1 },
  llm: { inputs: 1, outputs: 1 },
  prompt_template: { inputs: 1, outputs: 1 },
  conditional: { inputs: 1, outputs: 2 },
  output: { inputs: 1, outputs: 0 },
  code: { inputs: 1, outputs: 1 },
  merge: { inputs: 2, outputs: 1 },
  shell: { inputs: 1, outputs: 1 },
  http_request: { inputs: 1, outputs: 1 },
  file_read: { inputs: 1, outputs: 1 },
  file_write: { inputs: 1, outputs: 1 },
  loop: { inputs: 1, outputs: 2 },
  hitl: { inputs: 1, outputs: 2 },
  react_agent: { inputs: 1, outputs: 1 },
  conversation_memory: { inputs: 1, outputs: 1 },
  map_reduce: { inputs: 1, outputs: 1 },
  embed: { inputs: 1, outputs: 1 },
  vector_store: { inputs: 1, outputs: 1 },
  rag_retrieve: { inputs: 1, outputs: 1 },
  ui_interface: { inputs: 0, outputs: 0 }
};

const nodeIcons = {
  start: '▶',
  llm: '🤖',
  prompt_template: '📝',
  conditional: '🔀',
  code: '💻',
  merge: '🔗',
  output: '📤',
  shell: '⌨',
  http_request: '🌐',
  file_read: '📂',
  file_write: '💾',
  loop: '🔁',
  hitl: '👤',
  react_agent: '🧠',
  conversation_memory: '💬',
  map_reduce: '⚡',
  embed: '🔢',
  vector_store: '🗄️',
  rag_retrieve: '🎯',
  ui_interface: '🖥️'
};

const nodeLabels = {
  start: 'Start',
  llm: 'LLM Call',
  prompt_template: 'Template',
  conditional: 'Condition',
  code: 'Code',
  merge: 'Merge',
  output: 'Output',
  shell: 'Shell',
  http_request: 'HTTP Request',
  file_read: 'File Read',
  file_write: 'File Write',
  loop: 'Loop',
  hitl: 'Human Review',
  react_agent: 'ReAct Agent',
  conversation_memory: 'Memory',
  map_reduce: 'Map-Reduce',
  embed: 'Embed',
  vector_store: 'Vector Store',
  rag_retrieve: 'RAG Retrieve',
  ui_interface: 'Interface'
};

document.addEventListener('DOMContentLoaded', () => {
  initEditor();
  initDragDrop();
  initToolbar();
  initKeyboardShortcuts();
  loadSettings();
  initResizeHandles();
});

function initEditor() {
  const container = document.getElementById('drawflow');
  editor = new Drawflow(container);
  editor.reroute = true;
  editor.reroute_fix_curvature = true;
  editor.start();

  editor.on('nodeSelected', (nodeId) => {
    selectedNodeId = nodeId;
    showNodeProperties(nodeId);
  });

  editor.on('nodeUnselected', () => {
    selectedNodeId = null;
    clearProperties();
  });

  editor.on('nodeRemoved', (nodeId) => {
    if (selectedNodeId === nodeId) {
      selectedNodeId = null;
      clearProperties();
    }
  });

  editor.on('connectionCreated', () => {});
  editor.on('connectionRemoved', () => {});
}

function initDragDrop() {
  document.querySelectorAll('.palette-node').forEach((el) => {
    el.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('nodeType', el.dataset.type || el.dataset.node || '');
      e.dataTransfer.effectAllowed = 'move';
    });
  });

  const canvas = document.getElementById('drawflow');

  canvas.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  });

  canvas.addEventListener('drop', (e) => {
    e.preventDefault();
    const type = e.dataTransfer.getData('nodeType');
    if (!type || !nodeTemplates[type]) return;

    const rect = canvas.getBoundingClientRect();
    const zoom = editor.zoom;
    const precanvas = editor.precanvas.getBoundingClientRect();
    const posX = (e.clientX - precanvas.left) / zoom;
    const posY = (e.clientY - precanvas.top) / zoom;

    addNode(type, posX, posY);
  });
}

function addNode(type, posX, posY) {
  const io = nodeIO[type];
  const data = JSON.parse(JSON.stringify(defaultNodeData[type]));
  const html = nodeTemplates[type];
  const nodeId = editor.addNode(
    type,
    io.inputs,
    io.outputs,
    posX,
    posY,
    'node-' + type,
    data,
    html
  );
  return nodeId;
}

function initToolbar() {
  document.getElementById('btn-new').addEventListener('click', newFlow);
  document.getElementById('btn-save').addEventListener('click', saveFlow);
  document.getElementById('btn-load').addEventListener('click', () => {
    loadFlowsList();
    openModal('flows-modal');
  });
  const examplesBtn = document.getElementById('btn-examples');
  if (examplesBtn) {
    examplesBtn.addEventListener('click', () => {
      loadExamplesList();
      openModal('examples-modal');
    });
  }
  document.getElementById('btn-run').addEventListener('click', runFlow);
  document.getElementById('btn-stop').addEventListener('click', stopExecution);
  document.getElementById('btn-export').addEventListener('click', exportFlow);
  document.getElementById('btn-settings').addEventListener('click', () => openModal('settings-modal'));
  const ideBtn = document.getElementById('btn-agent-ide');
  if (ideBtn) ideBtn.addEventListener('click', openAgentIde);
}

function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      saveFlow();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runFlow();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
      e.preventDefault();
      newFlow();
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedNodeId) {
      const active = document.activeElement;
      const isInput = active && (
        active.tagName === 'INPUT' ||
        active.tagName === 'TEXTAREA' ||
        active.tagName === 'SELECT'
      );
      if (!isInput) {
        editor.removeNodeId('node-' + selectedNodeId);
      }
    }
  });
}

/* ═══════════════ PROPERTIES PANEL ═══════════════ */

function clearProperties() {
  document.getElementById('properties-content').innerHTML =
    '<div class="properties-empty">Select a node to edit its properties</div>';
}

function getNodeData(nodeId) {
  return editor.drawflow.drawflow.Home.data[nodeId];
}

function setNodeDataField(nodeId, field, value) {
  editor.drawflow.drawflow.Home.data[nodeId].data[field] = value;
}

function updateNodeDisplay(nodeId) {
  const node = getNodeData(nodeId);
  if (!node) return;
  const type = node.name;
  const data = node.data;
  const el = document.querySelector('#node-' + nodeId + ' .df-node-info');
  if (!el) return;

  switch (type) {
    case 'start':
      el.textContent = data.input_text ? truncate(data.input_text, 25) : 'Entry point';
      break;
    case 'llm': {
      const parts = [];
      if (data.provider) parts.push(data.provider);
      if (data.model) parts.push(data.model);
      el.textContent = parts.length ? parts.join(' / ') : 'AI Model';
      break;
    }
    case 'prompt_template':
      el.textContent = data.template ? truncate(data.template, 25) : 'Prompt Template';
      break;
    case 'conditional':
      el.textContent = data.condition_value
        ? `${data.condition_type}: ${truncate(data.condition_value, 16)}`
        : 'True / False';
      break;
    case 'code':
      el.textContent = data.code ? truncate(data.code, 25) : 'Python';
      break;
    case 'merge':
      el.textContent = data.merge_mode || 'Combine inputs';
      break;
    case 'output':
      el.textContent = data.output_name || 'Result';
      break;
    case 'shell':
      el.textContent = data.command_template ? truncate(data.command_template, 25) : 'Run command';
      break;
    case 'http_request': {
      const m = data.method || 'GET';
      el.textContent = data.url_template ? `${m} ${truncate(data.url_template, 18)}` : m;
      break;
    }
    case 'file_read':
      el.textContent = data.file_path_template ? truncate(data.file_path_template, 25) : 'Read file';
      break;
    case 'file_write':
      el.textContent = data.file_path ? truncate(data.file_path, 25) : 'Write file';
      break;
    case 'loop':
      el.textContent = `${data.loop_mode || 'code'} × ${data.max_iterations || 5}`;
      break;
    case 'hitl':
      el.textContent = data.prompt_message ? truncate(data.prompt_message, 25) : 'Approval gate';
      break;
    case 'react_agent':
      el.textContent = data.goal ? truncate(data.goal, 25) : 'Autonomous agent';
      break;
    case 'conversation_memory':
      el.textContent = `${data.strategy || 'full'} (${data.max_messages || 50} msgs)`;
      break;
    case 'map_reduce':
      el.textContent = `${data.split_mode || 'newline'} → ${data.reduce_mode || 'concat'}`;
      break;
    case 'embed':
      el.textContent = `→ ${data.collection || 'default'}`;
      break;
    case 'vector_store':
      el.textContent = `${data.operation || 'query'} · ${data.collection || 'default'}`;
      break;
    case 'rag_retrieve':
      el.textContent = `Top ${data.top_k || 5} · ${data.collection || 'default'}`;
      break;
    case 'ui_interface':
      if (window.currentFlowId) {
        el.innerHTML = `<span style="opacity:0.7">${data.mode || 'chat'} · ${data.title || 'App'}</span><a href="/app/${window.currentFlowId}" target="_blank" class="node-app-link" onclick="event.stopPropagation()">🚀 Open App</a>`;
      } else {
        el.innerHTML = `<span style="opacity:0.7">${data.mode || 'chat'} · ${data.title || 'App'}</span><span class="node-app-link" style="opacity:0.5">Save flow first</span>`;
      }
      break;
  }

  const headerLabel = document.querySelector('#node-' + nodeId + ' .df-node-header span:nth-child(2)');
  if (headerLabel) {
    headerLabel.textContent = data.label || nodeLabels[type] || type;
  }

  updateAppButton();
}

function updateAppButton() {
  let btn = document.getElementById('btn-open-app');
  const nodes = editor.export().drawflow.Home.data;
  const hasInterface = Object.values(nodes).some(n => n.name === 'ui_interface');

  if (hasInterface && window.currentFlowId) {
    if (!btn) {
      btn = document.createElement('button');
      btn.id = 'btn-open-app';
      btn.title = 'Open App Interface';
      btn.textContent = '🖥️ App';
      btn.addEventListener('click', () => {
        window.open('/app/' + window.currentFlowId, '_blank');
      });
      const toolbar = document.querySelector('.toolbar-center');
      if (toolbar) {
        const divider = document.createElement('div');
        divider.className = 'toolbar-divider';
        toolbar.appendChild(divider);
        toolbar.appendChild(btn);
      }
    }
  } else if (btn) {
    const prev = btn.previousElementSibling;
    if (prev && prev.classList.contains('toolbar-divider')) prev.remove();
    btn.remove();
  }
}

function truncate(str, max) {
  if (!str) return '';
  const firstLine = str.split('\n')[0];
  return firstLine.length > max ? firstLine.substring(0, max) + '…' : firstLine;
}

function showNodeProperties(nodeId) {
  const node = getNodeData(nodeId);
  if (!node) return;

  const type = node.name;
  const data = node.data;
  const container = document.getElementById('properties-content');
  let html = `<span class="prop-node-type ${type}">${nodeLabels[type] || type}</span>`;

  html += buildField('text', 'label', 'Label', data.label);

  switch (type) {
    case 'start':
      html += buildField('textarea', 'input_text', 'Input Text', data.input_text, { placeholder: 'Enter the starting input for the flow...' });
      break;

    case 'llm':
      html += buildField('select', 'provider', 'Provider', data.provider, {
        options: [
          { value: '', label: 'Use default' },
          { value: 'openai', label: 'OpenAI' },
          { value: 'anthropic', label: 'Anthropic' },
          { value: 'ollama', label: 'Ollama' }
        ]
      });
      html += buildModelField('model', 'Model', data.provider || '', data.model);
      html += buildField('textarea', 'system_prompt', 'System Prompt', data.system_prompt);
      html += buildField('textarea', 'user_prompt_template', 'User Prompt Template', data.user_prompt_template, { note: 'Use {{input}} for the incoming data' });
      html += buildField('range', 'temperature', 'Temperature', data.temperature, { min: 0, max: 2, step: 0.1 });
      html += buildField('number', 'max_tokens', 'Max Tokens', data.max_tokens, { min: 1, max: 100000 });
      break;

    case 'prompt_template':
      html += buildField('textarea', 'template', 'Template', data.template, { note: 'Use {{input}} for the incoming data', className: 'mono' });
      break;

    case 'conditional':
      html += buildField('select', 'condition_type', 'Condition Type', data.condition_type, {
        options: [
          { value: 'contains', label: 'Contains' },
          { value: 'not_contains', label: 'Not Contains' },
          { value: 'equals', label: 'Equals' },
          { value: 'not_equals', label: 'Not Equals' },
          { value: 'starts_with', label: 'Starts With' },
          { value: 'ends_with', label: 'Ends With' },
          { value: 'regex', label: 'Regex Match' }
        ]
      });
      html += buildField('text', 'condition_value', 'Condition Value', data.condition_value, { placeholder: 'Value to test against' });
      html += '<div class="form-group"><div class="form-note">Output 1 = True, Output 2 = False</div></div>';
      break;

    case 'output':
      html += buildField('text', 'output_name', 'Output Name', data.output_name, { placeholder: 'result' });
      break;

    case 'code':
      html += buildField('checkbox', 'unrestricted', 'Unrestricted Mode', data.unrestricted, {
        note: 'Allows imports, file I/O, and full Python access'
      });
      html += buildField('textarea', 'code', 'Code', data.code, {
        className: 'code-area',
        note: 'Use <code>input_data</code> for input, set <code>output</code> for result'
      });
      break;

    case 'shell':
      html += buildField('select', 'shell_type', 'Shell Type', data.shell_type, {
        options: [
          { value: 'powershell', label: 'PowerShell' },
          { value: 'bash', label: 'Bash' },
          { value: 'python', label: 'Python (-c)' }
        ]
      });
      html += buildField('textarea', 'command_template', 'Command', data.command_template, {
        className: 'code-area',
        placeholder: 'echo "Hello {{input}}"',
        note: 'Use {{input}} for incoming data. stdin also receives the input.'
      });
      html += buildField('number', 'timeout', 'Timeout (seconds)', data.timeout, { min: 1, max: 600 });
      html += buildField('text', 'working_directory', 'Working Directory', data.working_directory, { placeholder: 'Leave blank for current dir' });
      break;

    case 'http_request':
      html += buildField('select', 'method', 'Method', data.method, {
        options: [
          { value: 'GET', label: 'GET' },
          { value: 'POST', label: 'POST' },
          { value: 'PUT', label: 'PUT' },
          { value: 'PATCH', label: 'PATCH' },
          { value: 'DELETE', label: 'DELETE' }
        ]
      });
      html += buildField('text', 'url_template', 'URL', data.url_template, {
        placeholder: 'https://api.example.com/data?q={{input}}',
        note: 'Use {{input}} for incoming data'
      });
      html += buildField('textarea', 'headers_json', 'Headers (JSON)', data.headers_json, {
        className: 'mono',
        placeholder: '{"Authorization": "Bearer ..."}',
      });
      html += buildField('textarea', 'body_template', 'Body', data.body_template, {
        className: 'mono',
        placeholder: '{"query": "{{input}}"}',
        note: 'For POST/PUT/PATCH. Use {{input}} for incoming data.'
      });
      html += buildField('text', 'extract_path', 'Extract JSON Path', data.extract_path, {
        placeholder: 'data.results[0].text',
        note: 'Dot-notation path to extract from JSON response'
      });
      html += buildField('number', 'timeout', 'Timeout (seconds)', data.timeout, { min: 1, max: 120 });
      break;

    case 'file_read':
      html += buildField('text', 'file_path_template', 'File Path', data.file_path_template, {
        placeholder: 'path/to/file.txt or {{input}}',
        note: 'Use {{input}} for dynamic path from incoming data'
      });
      break;

    case 'file_write':
      html += buildField('text', 'file_path', 'File Path', data.file_path, {
        placeholder: 'output/result.txt'
      });
      html += buildField('select', 'write_mode', 'Write Mode', data.write_mode, {
        options: [
          { value: 'write', label: 'Overwrite' },
          { value: 'append', label: 'Append' }
        ]
      });
      html += '<div class="form-group"><div class="form-note">Incoming data is written to the file and passed through to the output.</div></div>';
      break;

    case 'merge':
      html += buildField('select', 'merge_mode', 'Merge Mode', data.merge_mode, {
        options: [
          { value: 'concatenate', label: 'Concatenate' },
          { value: 'json_array', label: 'JSON Array' }
        ]
      });
      html += `<div class="form-group" id="separator-group" style="${data.merge_mode !== 'concatenate' ? 'display:none' : ''}">`;
      html += `<label>Separator</label>`;
      html += `<input type="text" value="${escapeAttr(data.separator)}" onchange="onPropChange(${nodeId}, 'separator', this.value)" oninput="onPropChange(${nodeId}, 'separator', this.value)" />`;
      html += '</div>';
      break;

    case 'loop':
      html += buildField('select', 'loop_mode', 'Loop Mode', data.loop_mode, {
        options: [
          { value: 'code', label: 'Code (Python)' },
          { value: 'llm', label: 'LLM Call' },
          { value: 'shell', label: 'Shell Command' }
        ]
      });
      html += buildField('number', 'max_iterations', 'Max Iterations', data.max_iterations, { min: 1, max: 1000 });
      html += buildField('select', 'condition_type', 'Stop Condition', data.condition_type, {
        options: [
          { value: 'contains', label: 'Output Contains' },
          { value: 'not_contains', label: 'Output Not Contains' },
          { value: 'equals', label: 'Output Equals' },
          { value: 'not_equals', label: 'Output Not Equals' },
          { value: 'starts_with', label: 'Output Starts With' },
          { value: 'ends_with', label: 'Output Ends With' },
          { value: 'regex', label: 'Regex Match' }
        ]
      });
      html += buildField('text', 'condition_value', 'Condition Value', data.condition_value, {
        placeholder: 'Value to check each iteration'
      });
      html += buildField('number', 'loop_delay_ms', 'Delay Between Iterations (ms)', data.loop_delay_ms, { min: 0, max: 60000 });
      html += '<div class="form-group"><div class="form-note">Output 1 = condition met, Output 2 = max iterations reached</div></div>';

      html += `<div id="loop-code-section" style="${data.loop_mode !== 'code' ? 'display:none' : ''}">`;
      html += buildField('checkbox', 'unrestricted', 'Unrestricted Mode', data.unrestricted);
      html += buildField('textarea', 'loop_code', 'Loop Code', data.loop_code, {
        className: 'code-area',
        note: '<code>input_data</code> = current value, <code>iteration</code> = index, set <code>output</code>'
      });
      html += '</div>';

      html += `<div id="loop-llm-section" style="${data.loop_mode !== 'llm' ? 'display:none' : ''}">`;
      html += buildField('select', 'loop_provider', 'LLM Provider', data.loop_provider, {
        options: [
          { value: '', label: 'Use default' },
          { value: 'openai', label: 'OpenAI' },
          { value: 'anthropic', label: 'Anthropic' },
          { value: 'ollama', label: 'Ollama' }
        ]
      });
      html += buildModelField('loop_model', 'Model', data.loop_provider || '', data.loop_model);
      html += buildField('textarea', 'loop_system_prompt', 'System Prompt', data.loop_system_prompt);
      html += buildField('textarea', 'loop_user_template', 'User Template', data.loop_user_template, {
        note: '{{input}} = current value, {{iteration}} = loop index'
      });
      html += buildField('range', 'loop_temperature', 'Temperature', data.loop_temperature, { min: 0, max: 2, step: 0.1 });
      html += buildField('number', 'loop_max_tokens', 'Max Tokens', data.loop_max_tokens, { min: 1, max: 100000 });
      html += '</div>';

      html += `<div id="loop-shell-section" style="${data.loop_mode !== 'shell' ? 'display:none' : ''}">`;
      html += buildField('select', 'loop_shell_type', 'Shell Type', data.loop_shell_type, {
        options: [
          { value: 'powershell', label: 'PowerShell' },
          { value: 'bash', label: 'Bash' },
          { value: 'python', label: 'Python (-c)' }
        ]
      });
      html += buildField('textarea', 'loop_command', 'Command', data.loop_command, {
        className: 'code-area',
        note: '{{input}} = current value, {{iteration}} = loop index'
      });
      html += '</div>';
      break;

    case 'hitl':
      html += buildField('textarea', 'prompt_message', 'Prompt Message', data.prompt_message, {
        placeholder: 'Instructions shown to the reviewer...'
      });
      html += buildField('checkbox', 'allow_edit', 'Allow Edit', data.allow_edit, {
        note: 'When enabled, the reviewer can modify the data before approving'
      });
      html += buildField('number', 'timeout', 'Timeout (seconds)', data.timeout, { min: 10, max: 3600 });
      html += '<div class="form-group"><div class="form-note">Output 1 = approved, Output 2 = rejected/timeout</div></div>';
      break;

    case 'react_agent':
      html += buildField('textarea', 'goal', 'Agent Goal', data.goal, {
        placeholder: 'What should the agent accomplish?',
        note: 'If empty, uses the incoming input as the goal'
      });
      html += buildField('select', 'provider', 'Provider', data.provider, {
        options: [
          { value: '', label: 'Use default' },
          { value: 'openai', label: 'OpenAI' },
          { value: 'anthropic', label: 'Anthropic' },
          { value: 'ollama', label: 'Ollama' }
        ]
      });
      html += buildModelField('model', 'Model', data.provider || '', data.model);
      html += buildField('textarea', 'system_prompt', 'System Prompt (optional)', data.system_prompt, {
        note: 'Custom system prompt. Leave empty for default ReAct prompt.'
      });
      html += buildField('text', 'allowed_tools', 'Allowed Tools', data.allowed_tools, {
        note: 'Comma-separated: shell, code, http, file_read, file_write'
      });
      html += buildField('number', 'max_iterations', 'Max Iterations', data.max_iterations, { min: 1, max: 100 });
      html += buildField('range', 'temperature', 'Temperature', data.temperature, { min: 0, max: 2, step: 0.1 });
      html += buildField('number', 'max_tokens', 'Max Tokens', data.max_tokens, { min: 1, max: 100000 });
      break;

    case 'conversation_memory':
      html += buildField('text', 'memory_id', 'Memory ID', data.memory_id, {
        placeholder: 'Auto-generated if empty',
        note: 'Unique identifier for this memory store'
      });
      html += buildField('select', 'strategy', 'Strategy', data.strategy, {
        options: [
          { value: 'full', label: 'Full History' },
          { value: 'sliding_window', label: 'Sliding Window' },
          { value: 'summarize', label: 'Summarize & Forget' }
        ]
      });
      html += buildField('number', 'max_messages', 'Max Messages', data.max_messages, { min: 1, max: 10000 });
      html += buildField('select', 'role', 'Message Role', data.role, {
        options: [
          { value: 'user', label: 'User' },
          { value: 'assistant', label: 'Assistant' },
          { value: 'system', label: 'System' }
        ]
      });
      html += buildField('select', 'output_format', 'Output Format', data.output_format, {
        options: [
          { value: 'json', label: 'JSON Array' },
          { value: 'text', label: 'Text (role: content)' }
        ]
      });
      html += buildField('text', 'persist_path', 'Persist Path', data.persist_path, {
        placeholder: 'memory/chat.json',
        note: 'Optional file path to persist memory between runs'
      });
      break;

    case 'map_reduce':
      html += buildField('select', 'split_mode', 'Split Mode', data.split_mode, {
        options: [
          { value: 'newline', label: 'Split by Newline' },
          { value: 'json_array', label: 'JSON Array' },
          { value: 'csv', label: 'Comma-Separated' }
        ]
      });
      html += buildField('select', 'map_node_type', 'Map Operation', data.map_node_type, {
        options: [
          { value: 'code', label: 'Code (Python)' },
          { value: 'llm', label: 'LLM Call' },
          { value: 'shell', label: 'Shell Command' },
          { value: 'prompt_template', label: 'Prompt Template' }
        ]
      });
      html += buildField('textarea', 'map_code', 'Map Code / Template', JSON.stringify(data.map_node_data || {}, null, 2), {
        className: 'code-area',
        note: 'JSON config for the map operation node'
      });
      html += buildField('number', 'max_parallel', 'Max Parallel', data.max_parallel, { min: 1, max: 50 });
      html += buildField('select', 'reduce_mode', 'Reduce Mode', data.reduce_mode, {
        options: [
          { value: 'concatenate', label: 'Concatenate' },
          { value: 'json_array', label: 'JSON Array' },
          { value: 'json_merge', label: 'JSON Merge' },
          { value: 'custom_code', label: 'Custom Code' }
        ]
      });
      html += buildField('text', 'separator', 'Separator', data.separator, { placeholder: '\\n' });
      html += `<div id="reduce-code-section" style="${data.reduce_mode !== 'custom_code' ? 'display:none' : ''}">`;
      html += buildField('textarea', 'reduce_code', 'Reduce Code', data.reduce_code, {
        className: 'code-area',
        note: '<code>items</code> = list of map results, set <code>output</code>'
      });
      html += '</div>';
      break;

    case 'embed':
      html += buildField('text', 'collection', 'Collection', data.collection, {
        placeholder: 'default'
      });
      html += buildField('select', 'operation', 'Operation', data.operation, {
        options: [
          { value: 'embed_and_store', label: 'Embed & Store' },
          { value: 'embed_only', label: 'Embed Only (pass through)' }
        ]
      });
      html += buildField('number', 'chunk_size', 'Chunk Size (words)', data.chunk_size, {
        min: 0, note: '0 = no chunking (embed whole input)'
      });
      html += buildField('number', 'chunk_overlap', 'Chunk Overlap (words)', data.chunk_overlap, { min: 0 });
      html += buildField('textarea', 'metadata_json', 'Metadata (JSON)', data.metadata_json, {
        className: 'code-area', placeholder: '{"source": "user"}'
      });
      break;

    case 'vector_store':
      html += buildField('text', 'collection', 'Collection', data.collection, {
        placeholder: 'default'
      });
      html += buildField('select', 'operation', 'Operation', data.operation, {
        options: [
          { value: 'query', label: 'Query (semantic search)' },
          { value: 'insert', label: 'Insert' },
          { value: 'count', label: 'Count Documents' },
          { value: 'delete_all', label: 'Delete All' }
        ]
      });
      html += buildField('number', 'top_k', 'Top K Results', data.top_k, { min: 1, max: 100 });
      html += buildField('number', 'threshold', 'Similarity Threshold', data.threshold, {
        min: 0, max: 1, note: '0 = return all, 0.5+ = only strong matches'
      });
      html += buildField('textarea', 'metadata_json', 'Metadata Filter (JSON)', data.metadata_json, {
        className: 'code-area', placeholder: '{"role": "user"}'
      });
      break;

    case 'rag_retrieve':
      html += buildField('text', 'collection', 'Collection', data.collection, {
        placeholder: 'default'
      });
      html += buildField('number', 'top_k', 'Top K Results', data.top_k, { min: 1, max: 50 });
      html += buildField('number', 'threshold', 'Similarity Threshold', data.threshold, {
        min: 0, max: 1, note: '0.3 = moderate relevance filter'
      });
      html += buildField('select', 'output_format', 'Output Format', data.output_format, {
        options: [
          { value: 'context', label: 'Formatted Context' },
          { value: 'json', label: 'Raw JSON' }
        ]
      });
      break;

    case 'ui_interface':
      html += buildField('text', 'title', 'App Title', data.title, { placeholder: 'My App' });
      html += buildField('text', 'description', 'Description', data.description, { placeholder: 'What this app does' });
      html += buildField('select', 'mode', 'Interface Mode', data.mode, {
        options: [
          { value: 'chat', label: 'Chat (conversational)' },
          { value: 'form', label: 'Form (input → output)' }
        ]
      });
      html += buildField('select', 'theme', 'Theme', data.theme, {
        options: [
          { value: 'dark', label: 'Dark' },
          { value: 'light', label: 'Light' }
        ]
      });
      html += buildField('text', 'accent_color', 'Accent Color', data.accent_color, {
        placeholder: '#6366f1'
      });
      html += buildField('text', 'chat_history_path', 'Chat History File', data.chat_history_path, {
        placeholder: 'assistant/chat_history.json',
        note: 'Path to conversation memory JSON (chat mode)'
      });

      // Output node dropdown (populated from flow)
      html += '<div class="form-group"><label>Output Node</label><select data-field="output_node_key">';
      html += `<option value="">Auto (last result)</option>`;
      {
        const allNodes = editor.export().drawflow.Home.data;
        for (const [nid, n] of Object.entries(allNodes)) {
          if (n.name === 'output' || n.name === 'code' || n.name === 'llm' || n.name === 'merge' || n.name === 'prompt_template' || n.name === 'conversation_memory') {
            const lbl = n.data.label || nodeLabels[n.name] || n.name;
            const key = n.name + '_' + nid;
            const sel = key === data.output_node_key ? 'selected' : '';
            html += `<option value="${key}" ${sel}>${lbl} (#${nid})</option>`;
          }
        }
      }
      html += '</select><div class="form-note">Which node\'s output to show in the app</div></div>';

      html += buildField('select', 'show_thinking', 'Show Thinking', data.show_thinking ? 'true' : 'false', {
        options: [
          { value: 'false', label: 'Hide inner monologue' },
          { value: 'true', label: 'Show inner monologue' }
        ]
      });

      // Form field builder (visible in form mode)
      html += `<div class="form-group" id="field-builder-section" style="margin-top:16px;border-top:1px solid var(--border-color);padding-top:12px">
        <label style="font-size:12px;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-secondary)">Input Fields (Form Mode)</label>
        <div class="form-note" style="margin-bottom:8px">Define what the end user fills in. Each field becomes a variable in the flow.</div>
        <div id="interface-fields-list"></div>
        <button type="button" class="btn-small" onclick="addInterfaceField()" style="margin-top:6px;font-size:12px;padding:4px 10px;background:var(--accent);color:white;border:none;border-radius:4px;cursor:pointer">+ Add Field</button>
      </div>`;

      // Output display fields
      html += `<div class="form-group" id="output-fields-section" style="margin-top:12px;border-top:1px solid var(--border-color);padding-top:12px">
        <label style="font-size:12px;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-secondary)">Output Display (Form Mode)</label>
        <div class="form-note" style="margin-bottom:8px">Choose which results to show. Leave empty to show the main output.</div>
        <div id="interface-output-fields"></div>
        <button type="button" class="btn-small" onclick="addInterfaceOutputField()" style="margin-top:6px;font-size:12px;padding:4px 10px;background:var(--accent);color:white;border:none;border-radius:4px;cursor:pointer">+ Add Output</button>
      </div>`;

      if (window.currentFlowId) {
        html += `<div style="margin-top:16px"><a href="/app/${window.currentFlowId}" target="_blank" class="btn-primary" style="display:inline-block;padding:8px 16px;border-radius:6px;text-decoration:none;text-align:center">🚀 Open App</a></div>`;
      }
      break;
  }

  if (type !== 'start') {
    html += buildAdvancedSection(data);
  }

  container.innerHTML = html;
  bindPropEvents(nodeId, type);
  bindAdvancedToggle();
  bindLoopModeToggle();
  if (type === 'ui_interface') {
    renderInterfaceFields();
    renderInterfaceOutputFields();
  }
}

function buildField(fieldType, name, label, value, opts = {}) {
  let html = '<div class="form-group">';
  if (fieldType !== 'checkbox') {
    html += `<label>${label}</label>`;
  }

  switch (fieldType) {
    case 'text':
      html += `<input type="text" data-field="${name}" value="${escapeAttr(value || '')}" ${opts.placeholder ? `placeholder="${escapeAttr(opts.placeholder)}"` : ''} />`;
      break;
    case 'number':
      html += `<input type="number" data-field="${name}" value="${value || ''}" ${opts.min !== undefined ? `min="${opts.min}"` : ''} ${opts.max !== undefined ? `max="${opts.max}"` : ''} />`;
      break;
    case 'textarea':
      html += `<textarea data-field="${name}" class="${opts.className || ''}" ${opts.placeholder ? `placeholder="${escapeAttr(opts.placeholder)}"` : ''}>${escapeHtml(value || '')}</textarea>`;
      break;
    case 'select': {
      html += `<select data-field="${name}">`;
      (opts.options || []).forEach((opt) => {
        html += `<option value="${escapeAttr(opt.value)}" ${opt.value === value ? 'selected' : ''}>${escapeHtml(opt.label)}</option>`;
      });
      html += '</select>';
      break;
    }
    case 'range':
      html += '<div class="range-wrapper">';
      html += `<input type="range" data-field="${name}" value="${value}" min="${opts.min}" max="${opts.max}" step="${opts.step}" />`;
      html += `<span class="range-value" data-range-display="${name}">${value}</span>`;
      html += '</div>';
      break;
    case 'checkbox':
      html += `<label class="checkbox-wrapper"><input type="checkbox" data-field="${name}" ${value ? 'checked' : ''} /><span class="checkbox-label">${label}</span></label>`;
      label = '';
      break;
  }

  if (opts.note) {
    html += `<div class="form-note">${opts.note}</div>`;
  }

  html += '</div>';
  return html;
}

function buildModelField(fieldName, label, provider, currentModel) {
  const allModels = providerModels || {};
  const defaultModels = [{ value: '', label: 'Use default' }, { value: '_custom', label: '— Custom model —' }];
  let models;
  if (!provider) {
    models = defaultModels;
  } else {
    const pm = allModels[provider];
    if (pm) {
      models = [{ value: '', label: 'Use default' }, ...pm];
    } else {
      models = defaultModels;
    }
  }

  let matched = !currentModel || models.some(m => m.value === currentModel);
  let html = '<div class="form-group">';
  html += `<label>${label}</label>`;
  html += `<select data-field="${fieldName}" data-model-select="true">`;
  models.forEach(m => {
    const sel = (m.value === currentModel) ? 'selected' : (!matched && m.value === '_custom' ? 'selected' : '');
    html += `<option value="${escapeAttr(m.value)}" ${sel}>${escapeHtml(m.label)}</option>`;
  });
  html += '</select>';
  const showCustom = currentModel && !matched;
  html += `<input type="text" data-field="${fieldName}" data-model-custom="true" value="${escapeAttr(currentModel || '')}" placeholder="Enter model name..." style="margin-top:6px;${showCustom ? '' : 'display:none'}" />`;
  html += '</div>';
  return html;
}

function bindPropEvents(nodeId, type) {
  const container = document.getElementById('properties-content');

  container.querySelectorAll('input[data-field], textarea[data-field], select[data-field]').forEach((el) => {
    const field = el.dataset.field;

    const handler = () => {
      let val = el.value;
      if (el.type === 'checkbox') val = el.checked;
      if (el.type === 'number') val = parseFloat(val) || 0;
      if (el.type === 'range') {
        val = parseFloat(val);
        const display = container.querySelector(`[data-range-display="${field}"]`);
        if (display) display.textContent = val;
      }
      if (el.dataset.modelSelect) {
        const customInput = container.querySelector(`input[data-field="${field}"][data-model-custom]`);
        if (customInput) {
          if (val === '_custom') {
            customInput.style.display = '';
            customInput.focus();
            return;
          } else {
            customInput.style.display = 'none';
            customInput.value = '';
          }
        }
      }
      if (el.dataset.modelCustom) {
        setNodeDataField(nodeId, field, val);
        updateNodeDisplay(nodeId);
        return;
      }
      setNodeDataField(nodeId, field, val);
      updateNodeDisplay(nodeId);

      if (field === 'merge_mode') {
        const sep = document.getElementById('separator-group');
        if (sep) sep.style.display = val === 'concatenate' ? '' : 'none';
      }

      if (field === 'provider' || field === 'loop_provider') {
        const modelField = field === 'provider' ? 'model' : 'loop_model';
        const modelSel = container.querySelector(`select[data-field="${modelField}"][data-model-select]`);
        const modelCustom = container.querySelector(`input[data-field="${modelField}"][data-model-custom]`);
        if (modelSel) {
          const models = providerModels[val] || [];
          const allOpts = [{ value: '', label: 'Use default' }, ...models];
          if (!allOpts.some(m => m.value === '_custom')) allOpts.push({ value: '_custom', label: '— Custom model —' });
          modelSel.innerHTML = allOpts.map(m =>
            `<option value="${escapeAttr(m.value)}">${escapeHtml(m.label)}</option>`
          ).join('');
          modelSel.value = '';
          if (modelCustom) { modelCustom.style.display = 'none'; modelCustom.value = ''; }
          setNodeDataField(nodeId, modelField, '');
        }
      }
    };

    el.addEventListener('input', handler);
    el.addEventListener('change', handler);
  });
}

function onPropChange(nodeId, field, value) {
  setNodeDataField(nodeId, field, value);
  updateNodeDisplay(nodeId);
}

// ── Interface Field Builder ──

function renderInterfaceFields() {
  if (!selectedNodeId) return;
  const node = getNodeData(selectedNodeId);
  if (!node || node.name !== 'ui_interface') return;
  const fields = node.data.fields || [];
  const list = document.getElementById('interface-fields-list');
  if (!list) return;
  list.innerHTML = '';
  fields.forEach((f, i) => {
    const row = document.createElement('div');
    row.className = 'ifield-row';
    row.style.cssText = 'display:flex;gap:4px;margin-bottom:4px;align-items:center';
    row.innerHTML = `
      <input type="text" value="${escapeAttr(f.name || '')}" placeholder="var name" style="width:80px;font-size:11px;padding:4px 6px" data-ifield-idx="${i}" data-ifield-prop="name" />
      <input type="text" value="${escapeAttr(f.label || '')}" placeholder="Label" style="width:80px;font-size:11px;padding:4px 6px" data-ifield-idx="${i}" data-ifield-prop="label" />
      <select data-ifield-idx="${i}" data-ifield-prop="type" style="width:72px;font-size:11px;padding:4px 2px">
        <option value="text" ${f.type === 'text' ? 'selected' : ''}>Text</option>
        <option value="textarea" ${f.type === 'textarea' ? 'selected' : ''}>Textarea</option>
        <option value="number" ${f.type === 'number' ? 'selected' : ''}>Number</option>
        <option value="select" ${f.type === 'select' ? 'selected' : ''}>Dropdown</option>
      </select>
      <button type="button" onclick="removeInterfaceField(${i})" style="background:none;border:none;color:#f85149;cursor:pointer;font-size:14px;padding:0 4px" title="Remove">✕</button>
    `;
    if (f.type === 'select') {
      const optRow = document.createElement('div');
      optRow.style.cssText = 'margin-top:2px;margin-bottom:4px;margin-left:4px';
      optRow.innerHTML = `<input type="text" value="${escapeAttr(f.options || '')}" placeholder="opt1, opt2, opt3" style="width:100%;font-size:11px;padding:3px 6px" data-ifield-idx="${i}" data-ifield-prop="options" />`;
      list.appendChild(row);
      list.appendChild(optRow);
    } else {
      list.appendChild(row);
    }
  });
  list.querySelectorAll('[data-ifield-idx]').forEach(el => {
    el.addEventListener('input', () => {
      const idx = parseInt(el.dataset.ifieldIdx);
      const prop = el.dataset.ifieldProp;
      const node = getNodeData(selectedNodeId);
      if (!node) return;
      if (!node.data.fields) node.data.fields = [];
      if (node.data.fields[idx]) {
        node.data.fields[idx][prop] = el.value;
        editor.drawflow.drawflow.Home.data[selectedNodeId].data.fields = node.data.fields;
      }
    });
    el.addEventListener('change', () => {
      const idx = parseInt(el.dataset.ifieldIdx);
      const prop = el.dataset.ifieldProp;
      const node = getNodeData(selectedNodeId);
      if (!node) return;
      if (prop === 'type') {
        node.data.fields[idx].type = el.value;
        editor.drawflow.drawflow.Home.data[selectedNodeId].data.fields = node.data.fields;
        renderInterfaceFields();
      }
    });
  });
}

function addInterfaceField() {
  if (!selectedNodeId) return;
  const node = getNodeData(selectedNodeId);
  if (!node) return;
  if (!node.data.fields) node.data.fields = [];
  node.data.fields.push({ name: '', label: '', type: 'text', options: '' });
  editor.drawflow.drawflow.Home.data[selectedNodeId].data.fields = node.data.fields;
  renderInterfaceFields();
}

function removeInterfaceField(idx) {
  if (!selectedNodeId) return;
  const node = getNodeData(selectedNodeId);
  if (!node || !node.data.fields) return;
  node.data.fields.splice(idx, 1);
  editor.drawflow.drawflow.Home.data[selectedNodeId].data.fields = node.data.fields;
  renderInterfaceFields();
}

function renderInterfaceOutputFields() {
  if (!selectedNodeId) return;
  const node = getNodeData(selectedNodeId);
  if (!node || node.name !== 'ui_interface') return;
  const outputs = node.data.output_fields || [];
  const list = document.getElementById('interface-output-fields');
  if (!list) return;
  list.innerHTML = '';

  const allNodes = editor.export().drawflow.Home.data;
  const nodeOptions = [];
  for (const [nid, n] of Object.entries(allNodes)) {
    if (['output', 'code', 'llm', 'merge', 'prompt_template', 'conversation_memory', 'file_read', 'http_request', 'shell'].includes(n.name)) {
      nodeOptions.push({ key: n.name + '_' + nid, label: (n.data.label || nodeLabels[n.name] || n.name) + ' (#' + nid + ')' });
    }
  }

  outputs.forEach((o, i) => {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:4px;margin-bottom:4px;align-items:center';
    row.innerHTML = `
      <input type="text" value="${escapeAttr(o.label || '')}" placeholder="Display label" style="width:100px;font-size:11px;padding:4px 6px" data-ofield-idx="${i}" data-ofield-prop="label" />
      <select data-ofield-idx="${i}" data-ofield-prop="node_key" style="flex:1;font-size:11px;padding:4px 2px">
        ${nodeOptions.map(n => `<option value="${n.key}" ${n.key === o.node_key ? 'selected' : ''}>${n.label}</option>`).join('')}
      </select>
      <button type="button" onclick="removeInterfaceOutputField(${i})" style="background:none;border:none;color:#f85149;cursor:pointer;font-size:14px;padding:0 4px" title="Remove">✕</button>
    `;
    list.appendChild(row);
  });

  list.querySelectorAll('[data-ofield-idx]').forEach(el => {
    el.addEventListener('input', () => {
      const idx = parseInt(el.dataset.ofieldIdx);
      const prop = el.dataset.ofieldProp;
      const node = getNodeData(selectedNodeId);
      if (!node || !node.data.output_fields) return;
      node.data.output_fields[idx][prop] = el.value;
      editor.drawflow.drawflow.Home.data[selectedNodeId].data.output_fields = node.data.output_fields;
    });
    el.addEventListener('change', () => {
      const idx = parseInt(el.dataset.ofieldIdx);
      const prop = el.dataset.ofieldProp;
      const node = getNodeData(selectedNodeId);
      if (!node || !node.data.output_fields) return;
      node.data.output_fields[idx][prop] = el.value;
      editor.drawflow.drawflow.Home.data[selectedNodeId].data.output_fields = node.data.output_fields;
    });
  });
}

function addInterfaceOutputField() {
  if (!selectedNodeId) return;
  const node = getNodeData(selectedNodeId);
  if (!node) return;
  if (!node.data.output_fields) node.data.output_fields = [];
  node.data.output_fields.push({ label: '', node_key: '' });
  editor.drawflow.drawflow.Home.data[selectedNodeId].data.output_fields = node.data.output_fields;
  renderInterfaceOutputFields();
}

function removeInterfaceOutputField(idx) {
  if (!selectedNodeId) return;
  const node = getNodeData(selectedNodeId);
  if (!node || !node.data.output_fields) return;
  node.data.output_fields.splice(idx, 1);
  editor.drawflow.drawflow.Home.data[selectedNodeId].data.output_fields = node.data.output_fields;
  renderInterfaceOutputFields();
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function buildAdvancedSection(data) {
  const isOpen = (data.retry_count > 0 || (data.on_error && data.on_error !== 'stop'));
  let html = `<div class="advanced-toggle ${isOpen ? 'open' : ''}" onclick="toggleAdvanced(this)">`;
  html += `<span class="toggle-arrow">▶</span> Error Handling &amp; Retry`;
  html += '</div>';
  html += `<div class="advanced-body ${isOpen ? 'open' : ''}">`;
  html += buildField('number', 'retry_count', 'Retry Count', data.retry_count || 0, { min: 0, max: 20 });
  html += buildField('number', 'retry_delay_ms', 'Retry Delay (ms)', data.retry_delay_ms || 1000, { min: 0, max: 60000 });
  html += buildField('select', 'on_error', 'On Error', data.on_error || 'stop', {
    options: [
      { value: 'stop', label: 'Stop Flow' },
      { value: 'continue', label: 'Continue (empty output)' },
      { value: 'output_error', label: 'Output Error Message' }
    ]
  });
  html += '<div class="form-group"><div class="form-note"><b>Stop</b>: halts the flow. <b>Continue</b>: passes empty string. <b>Output Error</b>: passes error JSON to next node.</div></div>';
  html += '</div>';
  return html;
}

function toggleAdvanced(el) {
  el.classList.toggle('open');
  const body = el.nextElementSibling;
  if (body) body.classList.toggle('open');
}

function bindAdvancedToggle() {}

function bindLoopModeToggle() {
  const sel = document.querySelector('[data-field="loop_mode"]');
  if (!sel) return;
  sel.addEventListener('change', () => {
    const m = sel.value;
    const cs = document.getElementById('loop-code-section');
    const ls = document.getElementById('loop-llm-section');
    const ss = document.getElementById('loop-shell-section');
    if (cs) cs.style.display = m === 'code' ? '' : 'none';
    if (ls) ls.style.display = m === 'llm' ? '' : 'none';
    if (ss) ss.style.display = m === 'shell' ? '' : 'none';
  });
}

/* ═══════════════ HITL RESPONSE ═══════════════ */

function showHitlModal(nodeId, prompt, data, allowEdit) {
  pendingHitlNodeId = nodeId;
  document.getElementById('hitl-prompt').textContent = prompt;
  const textarea = document.getElementById('hitl-data');
  textarea.value = data;
  textarea.readOnly = !allowEdit;
  document.getElementById('hitl-modal').classList.remove('hidden');
}

function submitHitl(action) {
  if (!executionWs || !pendingHitlNodeId) return;
  const data = document.getElementById('hitl-data').value;
  executionWs.send(JSON.stringify({
    type: 'hitl_response',
    node_id: pendingHitlNodeId,
    action: action,
    data: data
  }));
  document.getElementById('hitl-modal').classList.add('hidden');
  setNodeStatus(pendingHitlNodeId, action === 'approve' ? 'complete' : 'error');
  appendLog(`  Human ${action === 'approve' ? 'approved' : 'rejected'} node ${pendingHitlNodeId}`, action === 'approve' ? 'success' : 'warning');
  pendingHitlNodeId = null;
}

/* ═══════════════ SAVE / LOAD / NEW ═══════════════ */

async function saveFlow() {
  try {
    const flowData = editor.export();
    const name = document.getElementById('flow-name').value || 'Untitled Flow';
    const body = { name, description: '', flow_data: flowData };

    if (currentFlowId) {
      const resp = await fetch(`/api/flows/${currentFlowId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!resp.ok) throw new Error('Failed to save flow');
    } else {
      const resp = await fetch('/api/flows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!resp.ok) throw new Error('Failed to create flow');
      const data = await resp.json();
      currentFlowId = data.id;
    }
    showToast('Flow saved!');
    refreshInterfaceLinks();
    updateAppButton();
  } catch (err) {
    showToast('Error saving flow: ' + err.message, 'error');
  }
}

function refreshAllNodeDisplays() {
  const nodes = editor.export().drawflow.Home.data;
  for (const nid of Object.keys(nodes)) {
    updateNodeDisplay(parseInt(nid));
  }
}

function refreshInterfaceLinks() {
  if (!currentFlowId) return;
  const nodes = editor.export().drawflow.Home.data;
  for (const [nid, node] of Object.entries(nodes)) {
    if (node.name === 'ui_interface') {
      updateNodeDisplay(parseInt(nid), 'ui_interface', node.data);
    }
  }
}

async function loadFlowsList() {
  const listEl = document.getElementById('flows-list');
  listEl.innerHTML = '<div class="flows-empty">Loading...</div>';

  try {
    const resp = await fetch('/api/flows');
    if (!resp.ok) throw new Error('Failed to load flows');
    const flows = await resp.json();

    if (!flows.length) {
      listEl.innerHTML = '<div class="flows-empty">No saved flows yet</div>';
      return;
    }

    listEl.innerHTML = flows.map((flow) => {
      const nodeCount = flow.node_count || 0;
      const date = flow.updated_at ? new Date(flow.updated_at).toLocaleString() : 'N/A';
      return `
        <div class="flow-item" onclick="loadFlow('${flow.id}')">
          <div class="flow-item-info">
            <div class="flow-item-name">${escapeHtml(flow.name)}</div>
            <div class="flow-item-meta">${nodeCount} nodes · Updated ${date}</div>
          </div>
          <div class="flow-item-actions">
            <button class="btn-danger-sm" onclick="event.stopPropagation(); deleteFlow('${flow.id}')">Delete</button>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    listEl.innerHTML = `<div class="flows-empty">Error loading flows: ${escapeHtml(err.message)}</div>`;
  }
}

function countFlowNodes(flowData) {
  if (!flowData || !flowData.drawflow || !flowData.drawflow.Home || !flowData.drawflow.Home.data) return 0;
  return Object.keys(flowData.drawflow.Home.data).length;
}

async function loadFlow(flowId) {
  try {
    const resp = await fetch(`/api/flows/${flowId}`);
    if (!resp.ok) throw new Error('Failed to load flow');
    const flow = await resp.json();

    editor.import(flow.flow_data);
    currentFlowId = flow.id;
    document.getElementById('flow-name').value = flow.name || 'Untitled Flow';
    closeModal('flows-modal');
    showToast('Flow loaded!');
    refreshAllNodeDisplays();
    updateAppButton();
  } catch (err) {
    showToast('Error loading flow: ' + err.message, 'error');
  }
}

async function deleteFlow(flowId) {
  if (!confirm('Delete this flow? This cannot be undone.')) return;
  try {
    const resp = await fetch(`/api/flows/${flowId}`, { method: 'DELETE' });
    if (!resp.ok) throw new Error('Failed to delete flow');
    if (currentFlowId === flowId) {
      currentFlowId = null;
      editor.clear();
      document.getElementById('flow-name').value = 'Untitled Flow';
    }
    loadFlowsList();
    showToast('Flow deleted');
  } catch (err) {
    showToast('Error deleting flow: ' + err.message, 'error');
  }
}

function newFlow() {
  editor.clear();
  currentFlowId = null;
  document.getElementById('flow-name').value = 'Untitled Flow';
  clearProperties();
  clearExecutionLog();
  updateAppButton();
  showToast('New flow created', 'info');
}

function importFlowGraph(graph, name) {
  editor.clear();
  currentFlowId = null;

  const idMap = {};
  for (const n of (graph.nodes || [])) {
    const type = n.type;
    if (!nodeTemplates[type]) continue;
    const io = nodeIO[type] || { inputs: 1, outputs: 1 };
    const data = { ...JSON.parse(JSON.stringify(defaultNodeData[type] || {})), ...(n.data || {}) };
    const nid = editor.addNode(
      type,
      io.inputs,
      io.outputs,
      n.x || 100,
      n.y || 200,
      'node-' + type,
      data,
      nodeTemplates[type]
    );
    idMap[n.id] = nid;
  }

  for (const c of (graph.connections || [])) {
    const from = idMap[c.from_node];
    const to = idMap[c.to_node];
    if (from && to) {
      try {
        editor.addConnection(from, to, c.from_output || 'output_1', c.to_input || 'input_1');
      } catch (_) {}
    }
  }

  document.getElementById('flow-name').value = name || 'Imported Flow';
  clearProperties();
  clearExecutionLog();
  refreshAllNodeDisplays();
  updateAppButton();
}

async function loadExamplesList() {
  const listEl = document.getElementById('examples-list');
  if (!listEl) return;
  listEl.innerHTML = '<div class="flows-empty">Loading examples...</div>';

  try {
    const resp = await fetch('/api/examples');
    if (!resp.ok) throw new Error('Failed to load examples');
    const examples = await resp.json();

    if (!examples.length) {
      listEl.innerHTML = '<div class="flows-empty">No tracked examples found</div>';
      return;
    }

    listEl.innerHTML = examples.map((example) => {
      const moduleList = (example.modules || []).join(', ');
      return `
        <div class="flow-item">
          <div class="flow-item-info" onclick="importExample('${escapeAttr(example.id)}')">
            <div class="flow-item-name">${escapeHtml(example.name)}</div>
            <div class="flow-item-meta">${escapeHtml(example.complexity || 'simple')} · ${example.node_count || 0} nodes</div>
            <div class="prompt-preview">${escapeHtml(example.description || '')}</div>
            <div class="flow-item-meta" style="margin-top:6px">${escapeHtml(moduleList)}</div>
          </div>
          <div class="flow-item-actions">
            <button class="btn-primary" onclick="event.stopPropagation(); importExample('${escapeAttr(example.id)}')">Load</button>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    listEl.innerHTML = `<div class="flows-empty">Error loading examples: ${escapeHtml(err.message)}</div>`;
  }
}

async function importExample(exampleId) {
  try {
    const resp = await fetch(`/api/examples/${exampleId}`);
    if (!resp.ok) throw new Error('Failed to load example');
    const example = await resp.json();
    importFlowGraph(example.flow_graph || {}, example.name || 'Example Flow');
    closeModal('examples-modal');
    showToast(`Example loaded: ${example.name || exampleId}`);
  } catch (err) {
    showToast('Error loading example: ' + err.message, 'error');
  }
}

/* ═══════════════ RUN / STOP ═══════════════ */

async function runFlow() {
  try {
    await saveFlow();
    if (!currentFlowId) return;

    const resp = await fetch(`/api/flows/${currentFlowId}/execute`, { method: 'POST' });
    if (!resp.ok) throw new Error('Failed to start execution');
    const { execution_id } = await resp.json();

    openExecutionPanel();
    clearExecutionLog();
    resetNodeStatuses();

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    executionWs = new WebSocket(`${protocol}//${location.host}/ws/execute/${execution_id}`);

    executionWs.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      handleExecutionMessage(msg);
    };

    executionWs.onerror = () => {
      appendLog('WebSocket connection error', 'error');
    };

    executionWs.onclose = () => {
      document.getElementById('btn-run').disabled = false;
      document.getElementById('btn-stop').disabled = true;
      executionWs = null;
    };

    document.getElementById('btn-run').disabled = true;
    document.getElementById('btn-stop').disabled = false;
  } catch (err) {
    showToast('Error running flow: ' + err.message, 'error');
  }
}

function stopExecution() {
  if (executionWs) {
    executionWs.close();
    executionWs = null;
  }
  document.getElementById('btn-run').disabled = false;
  document.getElementById('btn-stop').disabled = true;
  appendLog('Execution stopped by user', 'warning');
}

function handleExecutionMessage(msg) {
  switch (msg.type) {
    case 'node_start':
      appendLog(`▶ Starting: ${msg.node_name || msg.node_id}`, 'node-start');
      setNodeStatus(msg.node_id, 'running');
      break;

    case 'node_output':
      appendLog(`  ${msg.chunk || msg.output || ''}`, 'output');
      break;

    case 'node_complete':
      appendLog(`✓ Completed: ${msg.node_name || msg.node_id} (${msg.duration_ms || 0}ms)`, 'success');
      setNodeStatus(msg.node_id, 'complete');
      break;

    case 'node_error':
      appendLog(`✗ Error: ${msg.node_name || msg.node_id}: ${msg.error}`, 'error');
      setNodeStatus(msg.node_id, 'error');
      break;

    case 'node_error_handled':
      appendLog(`⚠ Error handled (${msg.action}): ${msg.node_id}: ${msg.error}`, 'error-handled');
      setNodeStatus(msg.node_id, 'complete');
      break;

    case 'hitl_waiting':
      appendLog(`🔔 Waiting for human review on node ${msg.node_id}`, 'warning');
      setNodeStatus(msg.node_id, 'waiting');
      showHitlModal(msg.node_id, msg.prompt, msg.data, msg.allow_edit);
      break;

    case 'flow_complete': {
      appendLog(`\nFlow completed in ${msg.duration_ms || 0}ms`, 'success');
      const resultsEl = document.getElementById('execution-results');
      if (msg.results) {
        resultsEl.textContent = typeof msg.results === 'string'
          ? msg.results
          : JSON.stringify(msg.results, null, 2);
      }
      break;
    }

    case 'flow_error':
      appendLog(`\nFlow error: ${msg.error}`, 'error');
      break;
  }
}

function setNodeStatus(nodeId, status) {
  const nodeEl = document.querySelector(`#node-${nodeId} .df-node-status`);
  if (nodeEl) {
    nodeEl.className = `df-node-status ${status}`;
  }
}

function resetNodeStatuses() {
  document.querySelectorAll('.df-node-status').forEach((el) => {
    el.className = 'df-node-status idle';
  });
  document.getElementById('execution-results').textContent = '';
}

/* ═══════════════ EXECUTION LOG ═══════════════ */

function appendLog(message, type = 'info') {
  const logEl = document.getElementById('execution-log');
  const entry = document.createElement('div');
  entry.className = `log-entry log-${type}`;
  entry.textContent = message;
  logEl.appendChild(entry);
  logEl.scrollTop = logEl.scrollHeight;
}

function clearExecutionLog() {
  document.getElementById('execution-log').innerHTML = '';
  document.getElementById('execution-results').textContent = '';
}

function toggleExecutionPanel() {
  const panel = document.getElementById('execution-panel');
  if (panel.classList.contains('collapsed')) {
    panel.classList.remove('collapsed');
    panel.classList.add('expanded');
    panel.style.height = '';
  } else {
    panel.classList.remove('expanded');
    panel.classList.add('collapsed');
    panel.style.height = '';
  }
}

function initResizeHandles() {
  // ── Properties panel: drag left edge to resize width ──
  const propsHandle = document.getElementById('props-resize-handle');
  const propsPanel = document.getElementById('properties-panel');
  if (propsHandle && propsPanel) {
    let dragging = false;
    let startX, startW;

    propsHandle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      dragging = true;
      startX = e.clientX;
      startW = propsPanel.offsetWidth;
      propsHandle.classList.add('active');
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      const dx = startX - e.clientX;
      const newW = Math.max(180, Math.min(startW + dx, window.innerWidth * 0.6));
      propsPanel.style.width = newW + 'px';
      propsPanel.style.minWidth = newW + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (!dragging) return;
      dragging = false;
      propsHandle.classList.remove('active');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    });
  }

  // ── Execution panel: drag top edge to resize height ──
  const execHandle = document.getElementById('exec-resize-handle');
  const execPanel = document.getElementById('execution-panel');
  if (execHandle && execPanel) {
    let dragging = false;
    let startY, startH;

    execHandle.addEventListener('mousedown', (e) => {
      e.preventDefault();
      if (execPanel.classList.contains('collapsed')) return;
      dragging = true;
      startY = e.clientY;
      startH = execPanel.offsetHeight;
      execPanel.classList.add('resizing');
      execHandle.classList.add('active');
      document.body.style.cursor = 'row-resize';
      document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      const dy = startY - e.clientY;
      const newH = Math.max(80, Math.min(startH + dy, window.innerHeight * 0.7));
      execPanel.style.height = newH + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (!dragging) return;
      dragging = false;
      execPanel.classList.remove('resizing');
      execHandle.classList.remove('active');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    });
  }
}

function openExecutionPanel() {
  const panel = document.getElementById('execution-panel');
  panel.classList.remove('collapsed');
  panel.classList.add('expanded');
}

/* ═══════════════ EXPORT ═══════════════ */

async function exportFlow() {
  if (!currentFlowId) {
    showToast('Save the flow first', 'error');
    return;
  }
  try {
    const resp = await fetch(`/api/flows/${currentFlowId}/export`);
    if (!resp.ok) throw new Error('Export failed');
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${document.getElementById('flow-name').value || 'flow'}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('Flow exported!');
  } catch (err) {
    showToast('Error exporting flow: ' + err.message, 'error');
  }
}

/* ═══════════════ MODEL CATALOG ═══════════════ */

const providerModels = {
  openai: [
    { value: 'gpt-4o',            label: 'GPT-4o (recommended)' },
    { value: 'gpt-4o-mini',       label: 'GPT-4o Mini (fast, cheap)' },
    { value: 'gpt-4-turbo',       label: 'GPT-4 Turbo' },
    { value: 'gpt-4',             label: 'GPT-4' },
    { value: 'gpt-3.5-turbo',     label: 'GPT-3.5 Turbo' },
    { value: 'o3-mini',           label: 'o3-mini (reasoning)' },
    { value: 'o1',                label: 'o1 (reasoning)' },
    { value: 'o1-mini',           label: 'o1-mini (reasoning, fast)' },
    { value: '_custom',           label: '— Custom model —' },
  ],
  anthropic: [
    { value: 'claude-sonnet-4-20250514',    label: 'Claude Sonnet 4 (recommended)' },
    { value: 'claude-3-7-sonnet-20250219',  label: 'Claude 3.7 Sonnet' },
    { value: 'claude-3-5-sonnet-20241022',  label: 'Claude 3.5 Sonnet' },
    { value: 'claude-3-5-haiku-20241022',   label: 'Claude 3.5 Haiku (fast, cheap)' },
    { value: 'claude-3-opus-20240229',      label: 'Claude 3 Opus' },
    { value: '_custom',                     label: '— Custom model —' },
  ],
  ollama: [
    { value: '_custom', label: '— Enter model name —' },
  ]
};

function getModelValue() {
  const sel = document.getElementById('setting-default-model-select');
  const txt = document.getElementById('setting-default-model');
  return sel.value === '_custom' ? txt.value : sel.value;
}

function populateModelDropdown(provider, currentModel) {
  const sel = document.getElementById('setting-default-model-select');
  const txt = document.getElementById('setting-default-model');
  const models = providerModels[provider] || providerModels.openai;

  sel.innerHTML = '';
  let matched = false;
  models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.value;
    opt.textContent = m.label;
    if (m.value === currentModel) {
      opt.selected = true;
      matched = true;
    }
    sel.appendChild(opt);
  });

  if (currentModel && !matched) {
    sel.value = '_custom';
    txt.value = currentModel;
    txt.style.display = '';
  } else {
    txt.style.display = sel.value === '_custom' ? '' : 'none';
    if (!currentModel && models.length > 1) sel.selectedIndex = 0;
  }
}

function onProviderChange() {
  const provider = document.getElementById('setting-default-provider').value;
  populateModelDropdown(provider, '');
}

function onModelSelectChange() {
  const sel = document.getElementById('setting-default-model-select');
  const txt = document.getElementById('setting-default-model');
  if (sel.value === '_custom') {
    txt.style.display = '';
    txt.focus();
  } else {
    txt.style.display = 'none';
    txt.value = '';
  }
}

/* ═══════════════ SETTINGS ═══════════════ */

async function loadSettings() {
  const hintOpenai = document.getElementById('setting-openai-key-hint');
  const hintAnthropic = document.getElementById('setting-anthropic-key-hint');
  try {
    const resp = await fetch('/api/settings');
    if (!resp.ok) return;
    const settings = await resp.json();

    if (settings.openai_api_key) document.getElementById('setting-openai-key').value = settings.openai_api_key;
    if (settings.anthropic_api_key) document.getElementById('setting-anthropic-key').value = settings.anthropic_api_key;
    if (settings.ollama_base_url) document.getElementById('setting-ollama-url').value = settings.ollama_base_url;
    if (settings.default_provider) document.getElementById('setting-default-provider').value = settings.default_provider;

    const provider = settings.default_provider || 'openai';
    populateModelDropdown(provider, settings.default_model || '');

    if (hintOpenai) {
      if (settings.openai_api_key_from_env) {
        hintOpenai.hidden = false;
        hintOpenai.textContent =
          'OPENAI_API_KEY is set in your environment (.env or system). It overrides any key stored in settings.json. Leave the field masked or empty to keep using it.';
      } else {
        hintOpenai.hidden = true;
        hintOpenai.textContent = '';
      }
    }
    if (hintAnthropic) {
      if (settings.anthropic_api_key_from_env) {
        hintAnthropic.hidden = false;
        hintAnthropic.textContent =
          'ANTHROPIC_API_KEY is set in your environment. It overrides any key stored in settings.json.';
      } else {
        hintAnthropic.hidden = true;
        hintAnthropic.textContent = '';
      }
    }
  } catch (_) {
    if (hintOpenai) {
      hintOpenai.hidden = true;
    }
    if (hintAnthropic) {
      hintAnthropic.hidden = true;
    }
  }
}

async function saveSettings() {
  const status = document.getElementById('settings-status');
  try {
    const body = {
      openai_api_key: document.getElementById('setting-openai-key').value,
      anthropic_api_key: document.getElementById('setting-anthropic-key').value,
      ollama_base_url: document.getElementById('setting-ollama-url').value,
      default_provider: document.getElementById('setting-default-provider').value,
      default_model: getModelValue()
    };

    const resp = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    if (!resp.ok) throw new Error('Failed to save settings');
    status.style.color = 'var(--accent-green)';
    status.textContent = 'Settings saved successfully';
    showToast('Settings saved!');
  } catch (err) {
    status.style.color = 'var(--accent-red)';
    status.textContent = 'Error: ' + err.message;
  }
}

async function testConnection() {
  const status = document.getElementById('settings-status');
  status.style.color = 'var(--accent-blue)';
  status.textContent = 'Testing connection...';

  try {
    const body = {
      provider: document.getElementById('setting-default-provider').value,
      model: getModelValue()
    };

    const resp = await fetch('/api/test-provider', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    const result = await resp.json();
    if (result.ok) {
      status.style.color = 'var(--accent-green)';
      status.textContent = result.message || 'Connection successful!';
    } else {
      status.style.color = 'var(--accent-red)';
      status.textContent = result.message || 'Connection failed';
    }
  } catch (err) {
    status.style.color = 'var(--accent-red)';
    status.textContent = 'Connection error: ' + err.message;
  }
}

/* ═══════════════ MODALS ═══════════════ */

function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
}

function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}

/* ═══════════════ TOAST NOTIFICATIONS ═══════════════ */

function ensureToastContainer() {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  return container;
}

function showToast(message, type = 'success') {
  const container = ensureToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentNode) toast.parentNode.removeChild(toast);
  }, 3000);
}

/* ═══════════════ CONTEXT MENU (Right-Click) ═══════════════ */

let contextMenu = null;

function initContextMenu() {
  contextMenu = document.getElementById('context-menu');
  document.getElementById('drawflow').addEventListener('contextmenu', (e) => {
    if (!selectedNodeId) return;
    e.preventDefault();
    contextMenu.style.left = e.clientX + 'px';
    contextMenu.style.top = e.clientY + 'px';
    contextMenu.classList.remove('hidden');
  });
  document.addEventListener('click', () => {
    if (contextMenu) contextMenu.classList.add('hidden');
  });
}

function contextTestNode() {
  if (!selectedNodeId) return;
  if (contextMenu) contextMenu.classList.add('hidden');
  const node = getNodeData(selectedNodeId);
  if (!node) return;
  document.getElementById('test-node-type').textContent = `${nodeLabels[node.name] || node.name} (Node ${selectedNodeId})`;
  document.getElementById('test-node-input').value = '';
  document.getElementById('test-node-output').textContent = '';
  document.getElementById('test-node-modal').dataset.nodeId = selectedNodeId;
  openModal('test-node-modal');
}

function contextToggleBreakpoint() {
  if (!selectedNodeId) return;
  if (contextMenu) contextMenu.classList.add('hidden');
  toggleBreakpoint(selectedNodeId);
}

async function runTestNode() {
  const nodeId = document.getElementById('test-node-modal').dataset.nodeId;
  const node = getNodeData(nodeId);
  if (!node) return;

  const inputText = document.getElementById('test-node-input').value;
  const outputEl = document.getElementById('test-node-output');
  outputEl.textContent = 'Running...';

  try {
    const resp = await fetch('/api/test-node', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        node_type: node.name,
        node_data: node.data,
        input_text: inputText,
      })
    });
    const result = await resp.json();
    if (result.ok) {
      outputEl.textContent = result.stream || result.output || '(empty output)';
    } else {
      outputEl.textContent = 'Error: ' + (result.error || 'Unknown error');
    }
  } catch (err) {
    outputEl.textContent = 'Error: ' + err.message;
  }
}

/* ═══════════════ DEBUG MODE (Step-Through) ═══════════════ */

let debugWs = null;
let debugBreakpoints = new Set();
let isDebugging = false;

function toggleBreakpoint(nodeId) {
  const nid = String(nodeId);
  const dotEl = document.querySelector(`#node-${nid} .df-node-breakpoint`);
  if (debugBreakpoints.has(nid)) {
    debugBreakpoints.delete(nid);
    if (dotEl) dotEl.remove();
  } else {
    debugBreakpoints.add(nid);
    if (!dotEl) {
      const nodeEl = document.querySelector(`#node-${nid} .df-node-header`);
      if (nodeEl) {
        const dot = document.createElement('span');
        dot.className = 'df-node-breakpoint';
        dot.title = 'Breakpoint';
        nodeEl.insertBefore(dot, nodeEl.firstChild);
      }
    }
  }
}

async function startDebug() {
  try {
    await saveFlow();
    if (!currentFlowId) return;

    const resp = await fetch(`/api/flows/${currentFlowId}/debug`, { method: 'POST' });
    if (!resp.ok) throw new Error('Failed to start debug');
    const { execution_id } = await resp.json();

    isDebugging = true;
    openExecutionPanel();
    clearExecutionLog();
    resetNodeStatuses();
    showDebugControls(true);

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    debugWs = new WebSocket(`${protocol}//${location.host}/ws/debug/${execution_id}`);

    debugWs.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      handleDebugMessage(msg);
    };

    debugWs.onerror = () => appendLog('Debug WebSocket error', 'error');
    debugWs.onclose = () => {
      isDebugging = false;
      debugWs = null;
      showDebugControls(false);
    };

    document.getElementById('btn-run').disabled = true;
    document.getElementById('btn-debug').disabled = true;
  } catch (err) {
    showToast('Error starting debug: ' + err.message, 'error');
  }
}

function handleDebugMessage(msg) {
  switch (msg.type) {
    case 'debug_pause': {
      setNodeStatus(msg.node_id, 'waiting');
      appendLog(`⏸ Paused at: ${msg.node_name || msg.node_id}`, 'warning');
      const inspector = document.getElementById('debug-inspector');
      if (inspector) {
        inspector.classList.remove('hidden');
        document.getElementById('debug-node-name').textContent = msg.node_name || msg.node_id;
        document.getElementById('debug-node-type').textContent = msg.node_type;
        document.getElementById('debug-input-data').value = msg.input_data || '';
      }
      break;
    }
    default:
      handleExecutionMessage(msg);
  }
}

function debugStep() {
  if (!debugWs) return;
  const editedInput = document.getElementById('debug-input-data').value;
  debugWs.send(JSON.stringify({ type: 'debug_step', input_data: editedInput }));
  document.getElementById('debug-inspector').classList.add('hidden');
}

function debugContinue() {
  if (!debugWs) return;
  debugWs.send(JSON.stringify({
    type: 'debug_continue',
    breakpoints: Array.from(debugBreakpoints)
  }));
  document.getElementById('debug-inspector').classList.add('hidden');
}

function debugStop() {
  if (debugWs) {
    debugWs.send(JSON.stringify({ type: 'debug_stop' }));
    debugWs.close();
    debugWs = null;
  }
  isDebugging = false;
  showDebugControls(false);
  document.getElementById('btn-run').disabled = false;
  document.getElementById('btn-debug').disabled = false;
  appendLog('Debug stopped by user', 'warning');
}

function debugEditAndStep() {
  if (!debugWs) return;
  const editedInput = document.getElementById('debug-input-data').value;
  debugWs.send(JSON.stringify({ type: 'debug_edit', input_data: editedInput }));
  document.getElementById('debug-inspector').classList.add('hidden');
}

function showDebugControls(show) {
  const controls = document.getElementById('debug-controls');
  if (controls) controls.style.display = show ? 'flex' : 'none';
  document.getElementById('btn-run').disabled = show;
  document.getElementById('btn-debug').disabled = show;
  if (!show) {
    const inspector = document.getElementById('debug-inspector');
    if (inspector) inspector.classList.add('hidden');
  }
}

/* ═══════════════ VARIABLE INSPECTOR ═══════════════ */

let variableInspectorOpen = false;

function toggleVariableInspector() {
  variableInspectorOpen = !variableInspectorOpen;
  const panel = document.getElementById('variable-inspector');
  if (variableInspectorOpen) {
    panel.classList.remove('hidden');
    refreshVariableInspector();
  } else {
    panel.classList.add('hidden');
  }
}

function refreshVariableInspector() {
  const listEl = document.getElementById('variable-list');
  if (!listEl) return;

  const nodes = editor.drawflow.drawflow.Home.data;
  const varMap = {};

  for (const [nid, node] of Object.entries(nodes)) {
    const data = node.data || {};
    const label = data.label || nodeLabels[node.name] || node.name;

    const allText = JSON.stringify(data);
    const matches = allText.match(/\{\{(\w+)\}\}/g);
    if (matches) {
      for (const m of matches) {
        const varName = m.replace(/\{|\}/g, '');
        if (!varMap[varName]) varMap[varName] = { producers: [], consumers: [] };
        varMap[varName].consumers.push({ id: nid, label });
      }
    }

    if (node.name === 'start' || node.name === 'code' || node.name === 'llm' ||
        node.name === 'prompt_template' || node.name === 'shell' || node.name === 'http_request') {
      if (!varMap['input']) varMap['input'] = { producers: [], consumers: [] };
      varMap['input'].producers.push({ id: nid, label });
    }
  }

  if (Object.keys(varMap).length === 0) {
    listEl.innerHTML = '<div class="var-empty">No variables found. Use {{variable}} in node templates.</div>';
    return;
  }

  let html = '';
  for (const [name, info] of Object.entries(varMap)) {
    html += `<div class="var-item" onclick="highlightVariable('${name}')">`;
    html += `<div class="var-name">{{${name}}}</div>`;
    if (info.producers.length) {
      html += `<div class="var-detail">Produced by: ${info.producers.map(p => p.label).join(', ')}</div>`;
    }
    if (info.consumers.length) {
      html += `<div class="var-detail">Used by: ${info.consumers.map(c => c.label).join(', ')}</div>`;
    }
    html += '</div>';
  }
  listEl.innerHTML = html;
}

function highlightVariable(varName) {
  document.querySelectorAll('.drawflow-node').forEach(el => el.classList.remove('var-highlighted'));

  const nodes = editor.drawflow.drawflow.Home.data;
  for (const [nid, node] of Object.entries(nodes)) {
    const allText = JSON.stringify(node.data || {});
    if (allText.includes(`{{${varName}}}`)) {
      const el = document.querySelector(`#node-${nid}`);
      if (el) el.classList.add('var-highlighted');
    }
  }

  setTimeout(() => {
    document.querySelectorAll('.var-highlighted').forEach(el => el.classList.remove('var-highlighted'));
  }, 3000);
}

/* ═══════════════ NL FLOW BUILDER ═══════════════ */

function openNLBuilder() {
  document.getElementById('nl-description').value = '';
  document.getElementById('nl-status').textContent = '';
  openModal('nl-builder-modal');
}

async function generateFlowFromDescription() {
  const description = document.getElementById('nl-description').value.trim();
  if (!description) {
    showToast('Enter a description first', 'error');
    return;
  }

  const statusEl = document.getElementById('nl-status');
  statusEl.textContent = 'Generating flow...';
  statusEl.style.color = 'var(--accent-blue)';

  try {
    const resp = await fetch('/api/generate-flow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description })
    });
    const result = await resp.json();

    if (!result.ok) {
      statusEl.textContent = 'Error: ' + result.error;
      statusEl.style.color = 'var(--accent-red)';
      return;
    }

    const graph = result.flow_graph;
    importFlowGraph(graph, 'Generated Flow');
    closeModal('nl-builder-modal');
    showToast('Flow generated! Review and adjust as needed.', 'success');
  } catch (err) {
    statusEl.textContent = 'Error: ' + err.message;
    statusEl.style.color = 'var(--accent-red)';
  }
}

/* ═══════════════ PROMPT LIBRARY ═══════════════ */

async function openPromptLibrary(insertTarget) {
  document.getElementById('prompt-library-modal').dataset.insertTarget = insertTarget || '';
  await loadPromptsList();
  openModal('prompt-library-modal');
}

async function loadPromptsList() {
  const listEl = document.getElementById('prompt-list');
  listEl.innerHTML = '<div class="flows-empty">Loading...</div>';

  try {
    const resp = await fetch('/api/prompts');
    if (!resp.ok) throw new Error('Failed to load prompts');
    const prompts = await resp.json();

    if (!prompts.length) {
      listEl.innerHTML = '<div class="flows-empty">No saved prompts yet. Add one below!</div>';
      return;
    }

    listEl.innerHTML = prompts.map(p => `
      <div class="flow-item prompt-item">
        <div class="flow-item-info" onclick="insertPrompt('${escapeAttr(p.id)}')">
          <div class="flow-item-name">${escapeHtml(p.name)}</div>
          <div class="flow-item-meta">${escapeHtml((p.tags || []).join(', '))} · ${escapeHtml(p.description || '')}</div>
          <div class="prompt-preview">${escapeHtml(truncate(p.template, 80))}</div>
        </div>
        <div class="flow-item-actions">
          <button class="btn-danger-sm" onclick="event.stopPropagation(); deletePrompt('${p.id}')">Delete</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    listEl.innerHTML = `<div class="flows-empty">Error: ${escapeHtml(err.message)}</div>`;
  }
}

async function savePromptToLibrary() {
  const name = document.getElementById('new-prompt-name').value.trim();
  const template = document.getElementById('new-prompt-template').value.trim();
  const tags = document.getElementById('new-prompt-tags').value.split(',').map(t => t.trim()).filter(Boolean);
  const description = document.getElementById('new-prompt-description').value.trim();

  if (!name || !template) {
    showToast('Name and template are required', 'error');
    return;
  }

  try {
    const resp = await fetch('/api/prompts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, template, tags, description })
    });
    if (!resp.ok) throw new Error('Failed to save prompt');
    showToast('Prompt saved to library!');
    document.getElementById('new-prompt-name').value = '';
    document.getElementById('new-prompt-template').value = '';
    document.getElementById('new-prompt-tags').value = '';
    document.getElementById('new-prompt-description').value = '';
    await loadPromptsList();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function insertPrompt(promptId) {
  try {
    const resp = await fetch('/api/prompts');
    const prompts = await resp.json();
    const prompt = prompts.find(p => p.id === promptId);
    if (!prompt) return;

    if (selectedNodeId) {
      const node = getNodeData(selectedNodeId);
      if (node) {
        const type = node.name;
        if (type === 'prompt_template') {
          setNodeDataField(selectedNodeId, 'template', prompt.template);
        } else if (type === 'llm') {
          setNodeDataField(selectedNodeId, 'user_prompt_template', prompt.template);
        } else if (type === 'react_agent') {
          setNodeDataField(selectedNodeId, 'system_prompt', prompt.template);
        }
        updateNodeDisplay(selectedNodeId);
        showNodeProperties(selectedNodeId);
      }
    }

    closeModal('prompt-library-modal');
    showToast('Prompt inserted!');
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function deletePrompt(promptId) {
  if (!confirm('Delete this prompt?')) return;
  try {
    await fetch(`/api/prompts/${promptId}`, { method: 'DELETE' });
    await loadPromptsList();
    showToast('Prompt deleted');
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

/* ═══════════════ SUB-FLOWS ═══════════════ */

async function saveAsSubflow() {
  if (contextMenu) contextMenu.classList.add('hidden');

  const selectedNodes = [];
  document.querySelectorAll('.drawflow-node.selected').forEach(el => {
    const id = el.id.replace('node-', '');
    selectedNodes.push(id);
  });

  if (selectedNodes.length === 0 && selectedNodeId) {
    selectedNodes.push(String(selectedNodeId));
  }

  if (selectedNodes.length === 0) {
    showToast('Select at least one node first', 'error');
    return;
  }

  const name = prompt('Sub-flow name:', 'My Sub-Flow');
  if (!name) return;

  const flowData = editor.export();
  const allNodes = flowData.drawflow.Home.data;

  const subFlowData = { drawflow: { Home: { data: {} } } };
  for (const nid of selectedNodes) {
    if (allNodes[nid]) {
      subFlowData.drawflow.Home.data[nid] = JSON.parse(JSON.stringify(allNodes[nid]));
    }
  }

  try {
    const resp = await fetch('/api/subflows', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        description: `Contains ${selectedNodes.length} nodes`,
        flow_data: subFlowData,
        input_ports: 1,
        output_ports: 1,
      })
    });
    if (!resp.ok) throw new Error('Failed to save sub-flow');
    showToast('Sub-flow saved!');
    await loadSubflowPalette();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function loadSubflowPalette() {
  const container = document.getElementById('subflow-palette');
  if (!container) return;

  try {
    const resp = await fetch('/api/subflows');
    if (!resp.ok) return;
    const subflows = await resp.json();

    if (!subflows.length) {
      container.innerHTML = '<div class="palette-empty">No sub-flows yet</div>';
      return;
    }

    container.innerHTML = subflows.map(sf => `
      <div class="palette-node subflow-item" onclick="loadSubflowOntoCanvas('${sf.id}')" title="${escapeAttr(sf.description || '')}">
        <span class="palette-icon" style="background:#9333ea">📦</span>
        <span>${escapeHtml(sf.name)}</span>
      </div>
    `).join('');
  } catch (_) {}
}

async function loadSubflowOntoCanvas(subflowId) {
  try {
    const resp = await fetch(`/api/subflows/${subflowId}`);
    if (!resp.ok) throw new Error('Failed to load sub-flow');
    const sf = await resp.json();

    const sfData = sf.flow_data || {};
    const nodes = sfData.drawflow?.Home?.data || {};

    let offsetX = 200, offsetY = 200;
    for (const [nid, node] of Object.entries(nodes)) {
      const type = node.name;
      if (!nodeTemplates[type]) continue;
      const io = nodeIO[type] || { inputs: 1, outputs: 1 };
      const data = { ...JSON.parse(JSON.stringify(defaultNodeData[type] || {})), ...(node.data || {}) };
      editor.addNode(type, io.inputs, io.outputs, (node.pos_x || 0) + offsetX, (node.pos_y || 0) + offsetY, 'node-' + type, data, nodeTemplates[type]);
    }

    showToast(`Sub-flow "${sf.name}" added to canvas`);
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

/* ═══════════════ AGENT IDE ═══════════════ */

function switchAgentIdeTab(tabId) {
  document.querySelectorAll('.agent-ide-tabs button').forEach((b) => {
    b.classList.toggle('active', b.getAttribute('data-agent-tab') === tabId);
  });
  document.querySelectorAll('.agent-ide-panel').forEach((p) => p.classList.add('hidden'));
  const panel = document.getElementById(`agent-ide-tab-${tabId}`);
  if (panel) panel.classList.remove('hidden');
}

function initAgentIdeTabs() {
  document.querySelectorAll('.agent-ide-tabs button').forEach((btn) => {
    btn.addEventListener('click', () => {
      const tab = btn.getAttribute('data-agent-tab');
      switchAgentIdeTab(tab);
      if (tab === 'persona') loadAgentIdePersonaEditor();
      if (tab === 'memory') loadAgentIdeMemoryEditor();
      if (tab === 'chat') refreshAgentIdeChat();
    });
  });
}

async function openAgentIde() {
  openModal('agent-ide-modal');
  switchAgentIdeTab('overview');
  await refreshAgentIdeOverview();
  loadAgentIdePersonaEditor();
  loadAgentIdeMemoryEditor();
}

async function refreshAgentIdeOverview() {
  const el = document.getElementById('agent-ide-overview-cards');
  const st = document.getElementById('agent-ide-overview-status');
  if (!el) return;
  st.textContent = 'Loading…';
  try {
    const resp = await fetch('/api/agent-ide/overview');
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    el.innerHTML = '';
    (data.sections || []).forEach((sec) => {
      const card = document.createElement('div');
      card.className = 'agent-ide-card';
      card.innerHTML = `<h4>${escapeHtml(sec.title || '')}</h4><div class="agent-ide-sub">${escapeHtml(sec.subtitle || '')}</div><pre>${escapeHtml(sec.body || '')}</pre>`;
      el.appendChild(card);
    });
    st.textContent = 'Updated.';
  } catch (e) {
    st.textContent = 'Error: ' + e.message;
    el.innerHTML = `<div class="agent-ide-card"><pre>${escapeHtml(String(e))}</pre></div>`;
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function loadAgentIdePersonaEditor() {
  const ta = document.getElementById('agent-ide-json-persona');
  const st = document.getElementById('agent-ide-persona-status');
  if (!ta) return;
  st.textContent = 'Loading…';
  try {
    const resp = await fetch('/api/agent-ide/document/persona');
    const data = await resp.json();
    ta.value = JSON.stringify(data, null, 2);
    st.textContent = 'Loaded.';
  } catch (e) {
    st.textContent = e.message;
  }
}

async function loadAgentIdeMemoryEditor() {
  const ta = document.getElementById('agent-ide-json-memory');
  const st = document.getElementById('agent-ide-memory-status');
  if (!ta) return;
  st.textContent = 'Loading…';
  try {
    const resp = await fetch('/api/agent-ide/document/memory_layers');
    const data = await resp.json();
    ta.value = JSON.stringify(data, null, 2);
    st.textContent = 'Loaded.';
  } catch (e) {
    st.textContent = e.message;
  }
}

async function saveAgentIdeDocument(name) {
  const id = name === 'persona' ? 'agent-ide-json-persona' : 'agent-ide-json-memory';
  const stId = name === 'persona' ? 'agent-ide-persona-status' : 'agent-ide-memory-status';
  const ta = document.getElementById(id);
  const st = document.getElementById(stId);
  if (!ta || !st) return;
  let body;
  try {
    body = JSON.parse(ta.value || '{}');
  } catch (e) {
    st.textContent = 'Invalid JSON: ' + e.message;
    return;
  }
  st.textContent = 'Saving…';
  try {
    const resp = await fetch(`/api/agent-ide/document/${name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(await resp.text());
    st.textContent = 'Saved.';
  } catch (e) {
    st.textContent = 'Error: ' + e.message;
  }
}

function truncateAgentChatContent(raw) {
  const s = String(raw);
  if (s.length <= 900) return s;
  return s.slice(0, 900) + '…';
}

async function refreshAgentIdeChat() {
  const list = document.getElementById('agent-ide-chat-list');
  const st = document.getElementById('agent-ide-chat-status');
  if (!list) return;
  st.textContent = 'Loading…';
  try {
    const resp = await fetch('/api/agent-ide/chat-history?limit=100');
    const data = await resp.json();
    list.innerHTML = '';
    const total = data.total ?? (data.messages || []).length;
    st.textContent = `Showing ${(data.messages || []).length} of ${total} messages`;
    (data.messages || []).forEach((m) => {
      const div = document.createElement('div');
      const role = m.role || '?';
      div.className = `agent-ide-msg ${role === 'user' ? 'user' : 'assistant'}`;
      let content = m.content;
      if (role === 'assistant' && typeof content === 'string' && content.trim().startsWith('{')) {
        try {
          const inner = JSON.parse(content);
          if (inner.response) content = inner.response;
        } catch (_) { /* keep raw */ }
      }
      const meta = `${role}${m.ts ? ' · ' + m.ts : ''}`;
      div.innerHTML = `<div class="meta">${escapeHtml(meta)}</div><div>${escapeHtml(truncateAgentChatContent(content))}</div>`;
      list.appendChild(div);
    });
  } catch (e) {
    st.textContent = e.message;
    list.innerHTML = `<pre>${escapeHtml(String(e))}</pre>`;
  }
}

async function runAgentIdeConsolidate(dryRun) {
  const out = document.getElementById('agent-ide-consolidate-result');
  if (out) out.textContent = dryRun ? 'Dry run…' : 'Running…';
  try {
    const resp = await fetch('/api/memory/consolidate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dry_run: dryRun, embed_insights: true }),
    });
    const data = await resp.json();
    if (out) out.textContent = JSON.stringify(data, null, 2);
    refreshAgentIdeOverview();
  } catch (e) {
    if (out) out.textContent = String(e);
  }
}

/* ═══════════════ INIT ADDITIONS ═══════════════ */

const _origDOMContentLoaded = () => {
  initContextMenu();
  loadSubflowPalette();
  initAgentIdeTabs();

  const debugBtn = document.getElementById('btn-debug');
  if (debugBtn) debugBtn.addEventListener('click', startDebug);

  const varBtn = document.getElementById('btn-variables');
  if (varBtn) varBtn.addEventListener('click', toggleVariableInspector);

  const nlBtn = document.getElementById('btn-nl-builder');
  if (nlBtn) nlBtn.addEventListener('click', openNLBuilder);

  const promptBtn = document.getElementById('btn-prompt-library');
  if (promptBtn) promptBtn.addEventListener('click', () => openPromptLibrary());
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', _origDOMContentLoaded);
} else {
  _origDOMContentLoaded();
}
