# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Workshop estimators and mechanics assessing vehicle damage beside a vehicle
and at a quote desk, using both mobile and desktop screens.

## Product Purpose

PanelScan turns a damage photo and a spoken assessment into an itemized repair
estimate, helping workshop staff prepare and review a quote.

## Positioning

PanelScan combines a mechanic's voice memo, damage-photo segmentation, and
Muse Spark synthesis into one estimate that a qualified person reviews.

## Operating Context

The assessment starts with a vehicle photo and a spoken or uploaded audio
memo. Shop-floor use may happen beside a damaged vehicle; quote review may
happen later at a desktop.

## Capabilities and Constraints

- Accept one damage image and one voice memo per assessment.
- Convert browser audio to mono 24 kHz PCM WAV for transcription.
- Return vehicle summary, itemized damage, estimated parts cost in ZAR, and
  labor hours.
- Every estimate is provisional until the workshop reviews and approves it.
- Prices are estimates, not supplier-verified quotes.
- Sharing is only enabled after a mechanic reviews every finding, enters the
  workshop's hourly labour rate, and explicitly approves the estimate.
- A private customer link records one approval or change request and expires
  after 30 days. It does not collect a signature or authorize repairs.
- Approval records contain the estimate and decision only; source media is not
  persisted by this handoff.

## Evidence on Hand

- Existing app flow and response schema: `frontend/src/App.tsx`,
  `backend/app/schemas.py`.
- No verified supplier pricing data or customer testimonials are present.

## Product Principles

- Make it quick to capture evidence beside a vehicle.
- Keep image, voice notes, and generated findings connected.
- Make uncertain AI outputs legible and reviewable.
- Do not present estimated prices as verified quotes.
- Turn a reviewed estimate into a clear customer decision and a workshop
  follow-up, without implying that approval alone starts work.

## Visual direction

- Direction: Southern African road atlas, selected by the user.
- Palette: contour ground `#E6EADD`, paper `#FBFCF8`, deep green ink
  `#173B38`, route blue `#3158B8`, and signal orange `#E96D32`.
- Typography: self-hosted Barlow Condensed for headings and DM Sans for
  interface text.
- Signature move: one route line connects Photo, Voice note, Estimate, and
  Customer. Progress reflects evidence added, an estimate returned, or an
  approval link created; it does not imply a customer decision or authorization
  to begin repairs.
- The screen remains a familiar assessment app, not a map, printed form, or
  dashboard costume. Every estimate is visibly marked as provisional until
  workshop approval.
- Design seed reference: `seed:275f225a487fcfc0`.
