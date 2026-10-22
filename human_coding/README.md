# Human verification coding

The arm registered in section 5.4 of the preregistration: a human rater codes
a random subsample under exactly the inputs the two models received, so the
study can report model-to-human agreement and not only model-to-model.

## Doing the coding

1. Start the local server (the page fetches `subsample.json`, which a
   `file://` page is not allowed to do):

   ```bash
   python3 -m http.server 8787
   ```

2. Open <http://localhost:8787/human_coding/rate.html>.

3. Code the 100 videos. Number keys choose an option and move to the next
   question; the last question moves to the next video. Arrow keys move
   between videos, Backspace goes back a question, clicking a frame enlarges
   it. Progress is saved in the browser after every answer, so stopping and
   resuming is safe.

4. Press **내보내기** and save the file as
   `human_coding/human_codes.json`.

The page never shows the model's codes. Do not look them up while coding: the
comparison is only worth reporting if the two ratings are independent.

Partial coding is fine — the ingest step accepts any number of completed
videos above its floor and ignores the rest.

## Folding it into the paper

```bash
python scripts/ingest_human_codes.py
python scripts/05_reliability.py --config config/config.main.yaml
python scripts/make_figures.py && python scripts/make_docx.py && python scripts/make_appendix.py
python scripts/audit_manuscript.py
```

`ingest_human_codes.py` validates every value against the codebook enums and
writes `data_main/06_human/human_codes.parquet` with the dtypes the models
used; a boolean stored as the string "true" would otherwise read as
disagreement with every `True` the models recorded. Stage 5 then adds the
`human_agreement` block to the reliability report, and Table 2 and Figure 2
grow a fourth arm on their own.

## Regenerating the subsample

```bash
python scripts/make_human_subsample.py            # 100 videos, seed 20261018
```

The seed is fixed, so the draw is reproducible. `subsample.json` is not
committed because it embeds transcript text.
