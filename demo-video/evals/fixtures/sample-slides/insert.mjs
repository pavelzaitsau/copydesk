// The insert of the sample deck: opens the sample release page and speaks one line over it.
// An insert exports one async function that gets the kit; it resets what it changed in finally.
import { pathToFileURL } from 'node:url';

export default async function (kit) {
  await kit.page.goto(pathToFileURL(`${import.meta.dirname}/../release-page/index.html`).href + '?lang=en', { waitUntil: 'load' });
  try {
    await kit.narrate('i1a', { wait: true, pad: 300 });
  } finally {
    // The sample page keeps no state between runs, so there is nothing to reset.
  }
}
