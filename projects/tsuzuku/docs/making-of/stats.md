| Scope | Model | API turns | Input | Cache write | Cache read | Output |
|---|---|---:|---:|---:|---:|---:|
| all sessions | claude-fable-5-1 | 155 | 2,972 | 9,000,043 | 16,360,403 | 419,284 |
| all sessions | claude-opus-5-5 | 3,584 | 7,302 | 23,972,820 | 2,014,769,713 | 4,643,949 |
| all sessions | _all | 3,739 | 10,274 | 32,972,863 | 2,031,130,116 | 5,063,233 |
| Producer session / main | claude-opus-5-5 | 1,317 | 2,712 | 8,650,317 | 780,873,742 | 1,661,752 |
| Producer session / subagents | claude-fable-5-1 | 46 | 680 | 1,702,268 | 1,984,371 | 179,649 |
| Producer session / subagents | claude-opus-5-5 | 786 | 1,572 | 3,982,463 | 372,128,196 | 911,388 |
| Producer session / subagents | _all | 832 | 2,252 | 5,684,731 | 374,112,567 | 1,091,037 |
| Fable's paper world / main | claude-opus-5-5 | 1,307 | 2,670 | 10,611,832 | 818,822,855 | 1,785,872 |
| Fable's paper world / subagents | claude-fable-5-1 | 109 | 2,292 | 7,297,775 | 14,376,032 | 239,635 |
| Fable's paper world / subagents | claude-opus-5-5 | 174 | 348 | 728,208 | 42,944,920 | 284,937 |
| Fable's paper world / subagents | _all | 283 | 2,640 | 8,025,983 | 57,320,952 | 524,572 |

| Paid call | Calls | Detail |
|---|---:|---|
| elevenlabs:music.compose | 68 | seconds 2,425; model music_v2_5 ×68 |
| elevenlabs:sfx | 30 |  |
| elevenlabs:stems | 13 |  |
| elevenlabs:tts | 120 | chars 8,611; model eleven_v3 ×112; model eleven_multilingual_v2 ×8 |
| gemini:image | 8 | model gemini-3-pro-image ×8 |
| gemini:video-review | 4 | model gemini-3.1-pro-preview ×4 |
| higgsfield:bytedance/seedance-2.5/text-to-video | 11 | seconds 55 |
| openai:image | 180 | n 213, usage_input_tokens 296,041, usage_output_tokens 499,214, failed 3; model gpt-image-2.5-flare ×1; size 2160x3840 high ×19; model gpt-image-2.5-sunburst ×179; size 2160x3840 max ×1; size 1056x1056 high ×101; size 2880x2880 high ×2; size 1024x1024 high ×14; size 2160x2880 high ×1; size 3456x1944 high ×1; size 2880x2160 high ×3; size 3456x1936 high ×1; size 1392x1392 high ×6; size 3072x2304 high ×1; size 3840x2160 high ×2; size 3840x1280 high ×5; size 3840x1600 high ×2; size 2048x2560 high ×18; size 1696x1696 high ×1; size 768x768 high ×2 |
