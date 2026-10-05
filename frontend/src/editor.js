/* The visual editor: one entity picker per role, built on Home Assistant's own form. */

import { languageOf, t } from './i18n.js';
import { DEFAULT_MAX_HZ, ROLES, entityIdOf } from './model.js';

export const EDITOR_TAG = 'renson-arean-card-editor';

const ROLE_PREFIX = 'role_';

// Home Assistant loads its form elements lazily; asking a built-in card for
// its editor is the usual way to have them registered.
async function loadFormElements() {
  if (customElements.get('ha-form') || !window.loadCardHelpers) return;
  try {
    const helpers = await window.loadCardHelpers();
    const card = await helpers.createCardElement({ type: 'entities', entities: [] });
    if (card && card.constructor.getConfigElement) await card.constructor.getConfigElement();
  } catch (_err) {
    // Without the form the YAML editor still works.
  }
}

function schema(lang) {
  return [
    { name: 'title', selector: { text: {} } },
    {
      name: 'max_hz',
      selector: { number: { min: 30, max: 200, step: 1, mode: 'box', unit_of_measurement: 'Hz' } },
    },
    {
      name: 'quality',
      selector: {
        select: {
          mode: 'dropdown',
          options: [
            { value: 'detailed', label: t(lang, 'ed_quality_detailed') },
            { value: 'sketch', label: t(lang, 'ed_quality_sketch') },
          ],
        },
      },
    },
    ...ROLES.map((role) => ({
      name: ROLE_PREFIX + role.key,
      selector: { entity: { domain: role.domains } },
    })),
  ];
}

function toFormData(config) {
  const data = {
    title: config.title || '',
    max_hz: config.max_hz === undefined ? DEFAULT_MAX_HZ : config.max_hz,
    quality: config.quality || 'detailed',
  };
  for (const [role, ref] of Object.entries(config.entities || {})) {
    data[ROLE_PREFIX + role] = entityIdOf(ref) || '';
  }
  return data;
}

function toConfig(previous, data) {
  const config = { ...previous, max_hz: data.max_hz, quality: data.quality };
  if (data.title) config.title = data.title;
  else delete config.title;
  const before = previous.entities || {};
  const entities = {};
  for (const role of ROLES) {
    const entityId = data[ROLE_PREFIX + role.key];
    if (!entityId) continue;
    // Keep a hand-written {entity, attribute} while the entity is unchanged.
    const old = before[role.key];
    entities[role.key] = old && typeof old === 'object' && old.entity === entityId ? old : entityId;
  }
  config.entities = entities;
  return config;
}

export class RensonAreanCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  connectedCallback() {
    loadFormElements().then(() => this._render());
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this._form) {
      this._form = document.createElement('ha-form');
      this._form.addEventListener('value-changed', (event) => {
        event.stopPropagation();
        const config = toConfig(this._config, event.detail.value);
        this._config = config;
        this.dispatchEvent(
          new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true })
        );
      });
      this.appendChild(this._form);
    }
    const lang = languageOf(this._hass);
    if (lang !== this._lang) {
      this._lang = lang;
      this._form.schema = schema(lang);
      this._form.computeLabel = (field) =>
        field.name.startsWith(ROLE_PREFIX) ? t(lang, field.name) : t(lang, `ed_${field.name}`);
    }
    this._form.hass = this._hass;
    this._form.data = toFormData(this._config);
  }
}
