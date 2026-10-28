// Le Quartier · copies a day of the season (app/data/season/s1/tN.json) into the frontend, so the
// 3D stage reads the same words the Feuilleton prints. Run after editing the season:
//   node scripts/quartier/sync-scene.mjs t1 a
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, '..', '..');
const [episode = 't1', day = 'a'] = process.argv.slice(2);
const source = path.resolve(web, '..', 'app', 'data', 'season', 's1', `${episode}.json`);
const ep = JSON.parse(fs.readFileSync(source, 'utf8'));
const d = ep.days.find((x) => x.day === day);
if (!d) throw new Error(`No day ${day} in ${episode}`);

const out = {
  source: `app/data/season/s1/${episode}.json`,
  episode: ep.id,
  number: ep.number,
  episode_title_fr: ep.title_fr,
  day: d.day,
  title_fr: d.title_fr,
  story_date_fr: d.story_date_fr,
  location_id: d.location_id,
  minutes: d.minutes,
  can_do: d.can_do,
  lexicon: d.lexicon,
  movements: d.movements,
};
const target = path.join(web, 'lib', 'quartier', 'scenes', `${episode}-${day}.json`);
fs.writeFileSync(target, `${JSON.stringify(out, null, 2)}\n`);
console.log(`wrote ${path.relative(web, target)} (${d.movements.length} movements)`);
