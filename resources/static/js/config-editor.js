/**
 * config-editor.js — Visual config editor driven by engine config schema.
 *
 * Usage:
 *   const editor = new ConfigEditor(container, schema, currentConfig, { apiFetch });
 *   editor.render();
 *   const config = editor.collect();
 */

export class ConfigEditor {
  /**
   * @param {HTMLElement} container
   * @param {Object} schema          — from GET /api/engines/{id}/config-schema
   * @param {Object} currentConfig   — current custom_config values
   * @param {Object} opts            — { apiFetch: fn(method, path, body) => data }
   */
  constructor(container, schema, currentConfig, opts = {}) {
    this.container = container;
    this.schema = schema;
    this.config = currentConfig || {};
    this.apiFetch = opts.apiFetch || (async () => ({}));
    this._libCache = {};
    this._showJson = false;
  }

  async render() {
    this.container.innerHTML = '';
    const fields = this.schema?.fields || [];
    if (!fields.length) {
      this.container.innerHTML = '<div style="color:var(--muted);font-size:.85rem">Нет настраиваемых полей</div>';
      return;
    }

    // Toggle button
    const toggleRow = el('div', { style: 'margin-bottom:12px;display:flex;gap:8px;align-items:center' });
    const toggleBtn = el('button', {
      className: 'btn btn-ghost btn-sm',
      textContent: 'Показать JSON',
      onclick: () => {
        this._showJson = !this._showJson;
        toggleBtn.textContent = this._showJson ? 'Визуальный редактор' : 'Показать JSON';
        this._renderMode();
      }
    });
    toggleRow.appendChild(toggleBtn);
    this.container.appendChild(toggleRow);

    // Visual editor area
    this._visualArea = el('div');
    this.container.appendChild(this._visualArea);

    // JSON editor area
    this._jsonArea = el('div', { style: 'display:none' });
    this._jsonTextarea = el('textarea', {
      rows: 12,
      style: 'width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:8px;font-family:monospace;font-size:.82rem;resize:vertical'
    });
    this._jsonArea.appendChild(this._jsonTextarea);
    this.container.appendChild(this._jsonArea);

    // Render visual fields
    for (const field of fields) {
      const fieldEl = await this._renderField(field);
      this._visualArea.appendChild(fieldEl);
    }

    this._renderMode();
  }

  _renderMode() {
    if (this._showJson) {
      this._visualArea.style.display = 'none';
      this._jsonArea.style.display = '';
      // Sync: collect visual → JSON
      this._jsonTextarea.value = JSON.stringify(this._collectVisual(), null, 2);
    } else {
      this._visualArea.style.display = '';
      this._jsonArea.style.display = 'none';
    }
  }

  collect() {
    if (this._showJson) {
      try {
        return JSON.parse(this._jsonTextarea.value);
      } catch {
        return this._collectVisual();
      }
    }
    return this._collectVisual();
  }

  _collectVisual() {
    const result = {};
    for (const field of (this.schema?.fields || [])) {
      const val = this._collectField(field);
      if (val !== undefined) result[field.key] = val;
    }
    return result;
  }

  _collectField(field) {
    const input = this._visualArea.querySelector(`[data-config-key="${field.key}"]`);
    if (!input) return this.config[field.key];

    switch (field.type) {
      case 'slug_picker':
        return input.value || null;
      case 'text':
        return input.value;
      case 'boolean':
        return input.checked;
      case 'number':
        return parseFloat(input.value) || 0;
      case 'key_value_map':
        return this._collectKeyValueMap(input, field);
      default:
        return input.value;
    }
  }

  _collectKeyValueMap(container, field) {
    const rows = container.querySelectorAll('.kvm-row');
    const result = {};
    rows.forEach(row => {
      const keyInput = row.querySelector('.kvm-key');
      const key = keyInput?.value?.trim();
      if (!key) return;
      const valuePickers = row.querySelectorAll('select.kvm-value');
      if (field.value_schema && Array.isArray(field.value_schema)) {
        const vals = Array.from(valuePickers).map(s => s.value || null);
        result[key] = vals.length === 1 ? vals[0] : vals;
      } else {
        result[key] = valuePickers[0]?.value || null;
      }
    });
    return result;
  }

  async _renderField(field) {
    const wrapper = el('div', { className: 'field', style: 'margin-bottom:14px' });
    const label = el('label', { textContent: field.label || field.key, style: 'display:block;font-size:.85rem;color:var(--muted);margin-bottom:4px' });
    wrapper.appendChild(label);

    switch (field.type) {
      case 'slug_picker':
        wrapper.appendChild(await this._renderSlugPicker(field));
        break;
      case 'text':
        wrapper.appendChild(this._renderText(field));
        break;
      case 'boolean':
        wrapper.appendChild(this._renderBoolean(field));
        break;
      case 'number':
        wrapper.appendChild(this._renderNumber(field));
        break;
      case 'key_value_map':
        wrapper.appendChild(await this._renderKeyValueMap(field));
        break;
      default:
        wrapper.appendChild(this._renderText(field));
    }
    return wrapper;
  }

  async _renderSlugPicker(field) {
    const select = el('select', {
      'data-config-key': field.key,
      style: 'width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:7px 10px;font-size:.875rem'
    });
    select.innerHTML = '<option value="">Загрузка...</option>';

    const libs = await this._loadLibraries(field.slug_type, field.engine_filter);
    select.innerHTML = '<option value="">(не выбрано)</option>';
    for (const lib of libs) {
      const opt = el('option', { value: lib.slug, textContent: `${lib.name} (${lib.slug})` });
      if (lib.slug === this.config[field.key]) opt.selected = true;
      select.appendChild(opt);
    }
    return select;
  }

  _renderText(field) {
    return el('input', {
      type: 'text',
      'data-config-key': field.key,
      value: this.config[field.key] || '',
      style: 'width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:7px 10px;font-size:.875rem'
    });
  }

  _renderBoolean(field) {
    const row = el('div', { style: 'display:flex;align-items:center;gap:8px' });
    const cb = el('input', {
      type: 'checkbox',
      'data-config-key': field.key,
      checked: !!this.config[field.key],
      style: 'width:auto'
    });
    row.appendChild(cb);
    row.appendChild(el('span', { textContent: field.label || field.key, style: 'font-size:.85rem' }));
    return row;
  }

  _renderNumber(field) {
    return el('input', {
      type: 'number',
      'data-config-key': field.key,
      value: this.config[field.key] ?? '',
      min: field.min ?? '',
      max: field.max ?? '',
      step: field.step ?? 'any',
      style: 'width:120px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:7px 10px;font-size:.875rem'
    });
  }

  async _renderKeyValueMap(field) {
    const container = el('div', { 'data-config-key': field.key });
    const currentVal = this.config[field.key] || {};

    // Pre-load libraries for value pickers
    const libsBySchema = [];
    if (Array.isArray(field.value_schema)) {
      for (const vs of field.value_schema) {
        if (vs.type === 'slug_picker') {
          libsBySchema.push(await this._loadLibraries(vs.slug_type, vs.engine_filter));
        } else {
          libsBySchema.push([]);
        }
      }
    }

    const addRow = (key = '', values = []) => {
      const row = el('div', {
        className: 'kvm-row',
        style: 'border:1px solid var(--border);border-radius:6px;padding:10px;margin-bottom:8px;background:var(--bg)'
      });

      // Header: key input + remove button
      const header = el('div', { style: 'display:flex;gap:6px;align-items:center;margin-bottom:8px' });
      const keyInput = el('input', {
        type: 'text',
        className: 'kvm-key',
        value: key,
        placeholder: field.key_label || 'Key',
        style: 'flex:1;background:var(--bg2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:5px 8px;font-size:.85rem;font-weight:600'
      });
      header.appendChild(keyInput);
      const rmBtn = el('button', {
        className: 'btn btn-danger btn-sm',
        textContent: '\u2715',
        onclick: () => row.remove()
      });
      header.appendChild(rmBtn);
      row.appendChild(header);

      // Value fields with labels
      if (Array.isArray(field.value_schema)) {
        field.value_schema.forEach((vs, i) => {
          const fieldWrap = el('div', { style: 'margin-bottom:6px' });
          if (vs.label) {
            fieldWrap.appendChild(el('div', {
              textContent: vs.label,
              style: 'font-size:.78rem;color:var(--muted);margin-bottom:2px'
            }));
          }
          const select = el('select', {
            className: 'kvm-value',
            style: 'width:100%;background:var(--bg2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:5px 8px;font-size:.85rem'
          });
          select.innerHTML = '<option value="">(не выбрано)</option>';
          const libs = libsBySchema[i] || [];
          const currentSlug = Array.isArray(values) ? values[i] : values;
          for (const lib of libs) {
            const opt = el('option', { value: lib.slug, textContent: lib.name });
            if (lib.slug === currentSlug) opt.selected = true;
            select.appendChild(opt);
          }
          fieldWrap.appendChild(select);
          row.appendChild(fieldWrap);
        });
      }

      container.insertBefore(row, addBtn);
    };

    const addBtn = el('button', {
      className: 'btn btn-ghost btn-sm',
      textContent: '+ Добавить',
      style: 'margin-top:4px',
      onclick: () => addRow()
    });
    container.appendChild(addBtn);

    // Populate existing values
    for (const [k, v] of Object.entries(currentVal)) {
      const vals = Array.isArray(v) ? v : [v];
      addRow(k, vals);
    }

    return container;
  }

  async _loadLibraries(slugType, engineFilter) {
    const cacheKey = `${slugType}|${engineFilter || ''}`;
    if (this._libCache[cacheKey]) return this._libCache[cacheKey];

    let url = `/api/libraries?lib_type=${encodeURIComponent(slugType || '')}`;
    if (engineFilter) url += `&engine_id=${encodeURIComponent(engineFilter)}`;

    const data = await this.apiFetch('GET', url);
    const libs = Array.isArray(data) ? data : [];
    this._libCache[cacheKey] = libs;
    return libs;
  }
}

function el(tag, props = {}) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'textContent') e.textContent = v;
    else if (k === 'innerHTML') e.innerHTML = v;
    else if (k === 'className') e.className = v;
    else if (k === 'checked') e.checked = v;
    else if (k === 'selected') e.selected = v;
    else if (k.startsWith('on')) e[k] = v;
    else if (k.startsWith('data-')) e.setAttribute(k, v);
    else e[k] = v;
  }
  return e;
}
