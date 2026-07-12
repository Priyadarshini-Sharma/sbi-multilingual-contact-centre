# Survey Methodology

## Overview

A primary survey was conducted to understand real customer experiences with SBI's customer care contact centre — specifically around language accessibility, IVR/keypad menu usability, wait times, and first-call resolution. Findings from this survey directly informed the design priorities of the multilingual contact centre routing engine in this project.

- **Sample size:** 65 respondents
- **Distribution method:** Shared through a mix of personal network and wider public sharing (not restricted to any single demographic or institution)
- **Anonymity:** Fully anonymous — no names, phone numbers, or identifying information were collected
- **Platform:** Google Forms
- **Original form:** https://forms.gle/i52EiKHTtpCxSfmt8
- **Raw response data:** [`Your_SBI_Experience__Your_Voice___.csv`](../data/Your_SBI_Experience__Your_Voice___.csv)

## Survey Questions

1. **What is your age group?**
2. **Which language do you prefer when speaking to a bank representative?**
3. **How often do you contact SBI customer care?**
4. **What is your primary reason for calling SBI customer care?**
5. **When you call SBI's toll-free number, how easy is it to navigate the keypad menu (press 1 for this, press 2 for that)?**
6. **Was your issue resolved on your first call without being transferred?**
7. **On average, how long do you wait before speaking to a human agent?**
8. **Have you ever abandoned a call because the wait was too long or the menu was too confusing?**
9. **Have you ever had difficulty because the available agent did not speak your preferred language?**

Full response options and the complete distribution for each question are available in the raw CSV (linked above) and visualized in [`sbi_survey_dashboard.png`](../docs/sbi_survey_dashboard.png).

## Key Findings (used to motivate system design)

- **83%** of respondents had abandoned a call at least occasionally due to long wait times or confusing menus
- Only **28%** reported getting first-call resolution "always" — most required multiple calls
- **43%** had faced friction due to a language mismatch with available agents (including respondents who reported defaulting to English specifically to avoid this issue)
- Respondents aged 41+ made up **63%** of the sample and reported disproportionately higher menu-navigation difficulty — directly motivating the system's focus on multilingual, low-friction routing for older customers

## Limitations

- Sample was self-selected (shared via personal/social channels) rather than randomly drawn from SBI's actual customer base, so findings should be read as directional/motivational rather than statistically representative of all SBI customers
- Sample size (n=65) is sufficient to identify clear patterns but not for fine-grained subgroup statistical significance
