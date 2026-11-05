# BAZE 12-image comparison

Scope: two-stage fretboard extraction, identical prompts/preprocessing. Ground truth not supplied to models.

| Model | Valid outputs | Mean IoU (failures=0) | Corner error px (successes) | Error / board width | Calls incl. retries | Input tokens | Output tokens | Total tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.5-flash | 11/12 | 0.7044 | 7.699 | 23.12% | 24 | 30,253 | 1,045 | 67,035 |
| gpt-6.1-sol | 12/12 | 0.9133 | 1.973 | 7.11% | 24 | 24,998 | 9,984 | 34,982 |
| claude-sonnet-5-5 | 12/12 | 0.8988 | 3.020 | 10.92% | 35 | 39,056 | 14,510 | 53,566 |

Additional Claude diagnostic: 796 tokens (577 input, 219 output).
Grand total: 156,379 reported tokens; 84 requests.

Single trial per image, except Claude format-failure retries; this is not a controlled repeated-trial benchmark.
Claude retry history and diagnostic usage are retained and included in accounting.
Manual labels score outputs only; they are not sent as prompts.
Token figures are reported by BAZE; provider image/reasoning accounting differs. No monetary cost inferred.
Gemini total_tokens exceeds prompt_tokens + completion_tokens by 35,737 tokens. The gateway did not provide a detailed breakdown; these tokens are retained in total usage, not assigned definitively to reasoning.
Convex valid output does not imply perfect accuracy. Failed geometry receives zero IoU.

## Per-image metrics

| Image | Gemini IoU / px | GPT IoU / px | Claude IoU / px |
|---|---:|---:|---:|
| 1051_5603_0000.jpg | 0.938 / 2.42 | 0.940 / 0.86 | 0.968 / 0.79 |
| 1051_5605_0000.jpg | 0.669 / 5.90 | 0.914 / 3.86 | 0.937 / 1.21 |
| 1347539285769.jpg | failed | 0.931 / 0.81 | 0.898 / 4.50 |
| 1350562795380.jpg | 0.679 / 4.22 | 0.855 / 1.55 | 0.895 / 1.46 |
| 2012032601357_0.jpg | 0.780 / 8.24 | 0.865 / 2.88 | 0.847 / 2.66 |
| 2015111201921_0.jpg | 0.889 / 3.01 | 0.992 / 0.54 | 0.940 / 1.29 |
| 201801031717219410_1.jpg | 0.859 / 2.76 | 0.881 / 1.99 | 0.912 / 2.45 |
| escgE1715241981.jpg | 0.819 / 32.25 | 0.885 / 5.35 | 0.808 / 10.66 |
| images (1).jpg | 0.656 / 6.10 | 0.917 / 1.42 | 0.810 / 4.12 |
| images (2).jpg | 0.581 / 5.84 | 0.909 / 1.13 | 0.912 / 1.51 |
| images.jpg | 0.912 / 2.20 | 0.938 / 1.27 | 0.943 / 2.67 |
| l_2014061102000525100136271.jpg | 0.670 / 11.77 | 0.934 / 2.03 | 0.916 / 2.92 |