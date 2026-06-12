# Phone-First Product Shell

## Ship Target

The fastest shippable mobile product is the responsive `web-frontend` as a mobile web/PWA. The live learning flows already live there, so the Expo `mobile/` app should stay secondary until native app store delivery, native-only sensors, or push packaging becomes the immediate requirement.

## Canonical Phone IA

Phone navigation has four primary destinations:

- Atelier
- Notebook
- Missions
- Feuilleton

Desktop navigation may expose secondary tools, but phone layout and flow decisions should start from these four tabs. Shared route ownership lives in `web-frontend/lib/product-shell.ts`.

## Product Rule

For core learning screens, prove the phone layout first. Desktop can then widen the same product model with additional columns, side panels, and secondary controls.
