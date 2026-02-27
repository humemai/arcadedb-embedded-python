# PVLDB Volume 19 — Formatting Guidelines (Essentials)

All papers submitted to PVLDB / VLDB 2026 (all tracks) must adhere strictly to the current PVLDB template (ACM-based). Deviations may lead to desk rejection.

## Template

Use the current PVLDB template:

- PVLDB style template (LaTeX) — zip
- PVLDB style template (LaTeX) — Overleaf project
- PVLDB style template (MS Word)

Because the template is updated regularly, you may be asked (especially at camera-ready time) to update to the latest style files.

## Submission Checklist (Must-Haves)

- Follow the PVLDB template exactly (format, line spacing, font size, caption style).
- No headers or footers (added later by the proceedings).
- No layout issues (no widows/orphans; no overfull boxes/line overflows).
- Last page columns balanced (LaTeX tip: `\usepackage{balance}`).
- Figures/tables are readable at normal zoom.
- Captions: table captions above tables; figure captions below figures.
- Bibliography uses `acmart` style; references are complete and alphabetically sorted.
- Author metadata matches CMT exactly (names, affiliations, order). Each author must have their own author tag; no “Additional Authors” section.
- No citations in the abstract; abstract must match the CMT abstract.
- PDF/A formatted, with all fonts embedded.

Submissions are made via CMT.

## Copyright & Camera-Ready (Accepted Papers)

All papers accepted for VLDB 2026 appear in PVLDB Volume 19. After acceptance, follow the camera-ready email instructions carefully. Key steps:

- Verify and, if needed, correct title/abstract/authors/affiliations/order in CMT (this becomes final).
- Update your sources to the current camera-ready style files.
- Fill in DOI and page numbers provided by the proceedings email:

	```tex
	\vldbdoi{XX.XX/XXX.XX}
	\vldbpages{XXX-XXX}
	```

- Fill in volume/issue/year provided by the proceedings email:

	```tex
	\vldbvolume{XXXX}
	\vldbissue{XXXX}
	\vldbyear{XXXX}
	```

- Re-check PDF compliance (template, no overflows, correct authors, PDF/A + embedded fonts).
- Complete and submit the PVLDB Copyright License Form.
- Name final files as instructed (example for submission id 42, author “Smith”):
	- Camera-ready paper: `p42-smith.pdf`
	- Copyright statement: `p42-smith_Copyright.pdf`

Submit the camera-ready paper and copyright statement via CMT.

## Publication Process (High-Level)

Accepted research papers are published continuously in monthly PVLDB issues. Expect roughly ~2 months from completion of camera-ready submission to publication.
