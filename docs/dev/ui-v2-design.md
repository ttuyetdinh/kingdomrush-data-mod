# UI v2: number boxes and half-width layout (design, 2026-11-08)

Owner requests collected after PR #1, built on branch feat/ui-number-boxes. The owner keeps the app beside the game at about half screen width and wants precise number entry instead of sliders.

## Decisions by the owner

1. Enemies and Troops become number boxes (top bar and Rules tab), typed or stepped with up/down buttons and arrow keys.
   - Enemies: multiplier from the list 0.25, 1, 2, ..., 10. 0.25 means a quarter (same per-stream behaviour as today; bosses always spawn).
   - Troops: extra soldiers per barracks, whole numbers. 0 = default, 1 = one more, -1 = one fewer. A minus larger than the barracks count leaves that barracks with no soldiers.
2. Layout C for a half-width window: two-row top bar when narrow, card list foldable with a « / » button, Apply buttons stay pinned, editor scrolls.
3. "5857/5857 values placed" moves under the title as a second line.
4. Level cells get up/down buttons and arrow keys. One step is the smallest digit of the game's original value (150: 1, 0.8: 0.1, 0.15: 0.01); Shift multiplies the step by 10.
5. Row sliders become Row % boxes (0% to 500%), same box style.
6. Quick scale sliders become % boxes, same rules as Row %.
7. The per-level panel (sliders, before/after bars, "Move all levels together") is removed, with the row expand arrows.
8. On wide tables the Stat column stays pinned left and the Row % column pinned right while levels scroll sideways.

## Calls made by the builder (owner can override)

- Troops range -10 to +10. Typed decimals round to the nearest whole number; out-of-range values clamp. A barracks (or upgrade level) whose game count is 0 stays at 0 for any Troops value, so no soldiers appear where the tower has none.
- Enemies: typed values between steps snap to the nearest allowed value (ties go up). Shift has no effect on Enemies and Troops.
- % boxes: 1% per step, 10% with Shift; typed values clamp to 0..500 and round to 0.1. A "mixed" box steps from 100%.
- Level cells: a value at or above 0 never steps below 0; each step saves at once like Enter.
- The top bar switches to two rows below 1280 px wide. The fold state of the card list is saved in settings.json in the app folder. Minimum window size 800 x 500.
- Old profiles: enemy_mult snaps to the new list; the old troop_mult setting is dropped (Troops starts at 0).
- The live file and the loader carry troop_delta instead of troop_mult.

## Approaches considered

- Number box: a shared SpinBox component (krmod/ui/spinbox.py) used by every box, with the step and parse rules in krmod/model/stepping.py. Chosen over the browser's native number input because native spinners can't do Shift x10, the 0.25 then 1 jump for Enemies, or the "mixed" state.
- Layout: three options were mocked (two-row top bar; one row with a tab dropdown and slide-out card list; two-row top bar with a foldable card list). The owner picked the third.

## Not verified in the game

- A barracks at 0 soldiers (Troops minus larger than the barracks count).
- Enemies x4 to x10 (spawn spacing, frame rate).
