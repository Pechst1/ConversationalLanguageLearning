// P12 · Home without Le Quartier's doors (launched 17 Nov): the roaming chip and the day card's
// second way into the scene. WP-81's budget (≤ 5 elements, ≤ 25 words, two chips) is the day's;
// the quarter's two doors are counted on their own in home.test.js (≤ 7 words, never a press).
// Shared by the Home tests that count words and chips.

const QUARTIER_CHIP = /<a class="av2-chip" data-chip="quartier"[\s\S]*?<\/a>/g;
const QUARTIER_WAY = /<a[^>]*data-scene-way="quartier"[^>]*>[\s\S]*?<\/a>/g;

const withoutQuartier = (html) =>
  html.replace(QUARTIER_CHIP, '').replace(QUARTIER_WAY, '').replace(/<div class="av2-home__section av2-home__chips"><\/div>/g, '');

module.exports = { QUARTIER_CHIP, QUARTIER_WAY, withoutQuartier };
