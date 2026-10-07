/* Tells the user to refresh when the browser runs another build of the card
 * than the integration serves. A browser can keep an older copy of Home
 * Assistant's page, and with it an older card, long after an update. */

import { t } from './i18n.js';

// The build replaces this with a hash of the built card; the integration
// reads it back from the file. Straight from src/ it stays as it is, and
// nothing is checked.
export const CARD_BUILD = '@@CARD_BUILD@@';

const BUILD_ID = /^[0-9a-f]{12}$/;

// Only a real difference counts: a card straight from src/, or an integration
// that does not answer, is not a reason to bother the user.
export function isOutdated(own, served) {
  return BUILD_ID.test(own) && BUILD_ID.test(served) && own !== served;
}

// Home Assistant's service worker answers a page from its store and fetches
// the new one in the background. Dropping this page from the store makes the
// reload fetch it from the server, instead of showing the old one once more.
async function reloadFresh() {
  try {
    const names = await caches.keys();
    await Promise.all(
      names.map(async (name) => (await caches.open(name)).delete(location.pathname, { ignoreSearch: true }))
    );
  } catch (_err) {
    // No store to clear: a plain reload is all there is.
  }
  location.reload();
}

function notify(element, lang) {
  // The toast is Home Assistant's own; it listens on its root element.
  (document.querySelector('home-assistant') || element).dispatchEvent(
    new CustomEvent('hass-notification', {
      detail: {
        message: t(lang, 'outdated'),
        action: { text: t(lang, 'refresh'), action: reloadFresh },
        duration: -1,
        dismissable: true,
      },
      bubbles: true,
      composed: true,
    })
  );
}

// Asks the integration which build is installed, now and each time the
// connection comes back: Home Assistant may have restarted with an update.
export function watchBuild(connection, own, onOutdated) {
  const ask = () => {
    connection
      .sendMessagePromise({ type: 'renson_arean/card_build' })
      .then((answer) => {
        if (isOutdated(own, answer && answer.build)) onOutdated();
      })
      // An integration without this command, or no integration at all.
      .catch(() => {});
  };
  ask();
  connection.addEventListener('ready', ask);
}

let watched = null;
let notified = false;
let language = 'en';

// Once per connection, however many cards there are; one message is enough.
export function checkBuild(element, hass, lang) {
  language = lang;
  const connection = hass.connection;
  if (!connection || connection === watched || !BUILD_ID.test(CARD_BUILD)) return;
  watched = connection;
  watchBuild(connection, CARD_BUILD, () => {
    if (notified) return;
    notified = true;
    notify(element, language);
  });
}
