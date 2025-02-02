Use this guide to produce **consistent, readable** HTML outputs across *all agents*, including the Workout Agents.  

---

## 1. Overall Structure

1. **Top-Level Heading**  
   - Use `<b>text</b>` for bold text.  
   - Example: `<b>🏋️‍♂️ Workout Generation - Jan 25, 2025</b>`

2. **Key Insights / Summary**  
   - Open with a short bullet list summarizing major points or recommended approach.  
   - For the Workout Agent, this could be 1–2 lines about the main goal of each workout option.

3. **Main Body**  
   - Divide the content into clearly-labeled sections (using `<b>text</b>`).  
   - Example sections for a workout plan:  
     - `<b>Warm-Up</b>`  
     - `<b>Main Set</b>`  
     - `<b>Cool-Down</b>`  
     - `<b>Intensity Targets</b>`  
   - Use bullets for step-by-step instructions.

4. **Conclusion / Next Steps**  
   - Summarize action items, restate recommended sessions, or mention any cautionary notes.

5. **Spacing**  
   - Keep a blank line between major sections and bullet groups.

---

## 2. Text Formatting Conventions

- **Bold**: `<b>text</b>` or `<strong>text</strong>`
- **Italic**: `<i>text</i>` or `<em>text</em>`
- **Underline**: `<u>text</u>` or `<ins>text</ins>`
- **Strikethrough**: `<s>text</s>`, `<strike>text</strike>`, or `<del>text</del>`
- **Spoiler**: `<tg-spoiler>text</tg-spoiler>`
- **Code**: `<code>text</code>` for inline, `<pre>text</pre>` for blocks
- **Links**: `<a href="url">text</a>`
- **Bullets**: Use • or - for primary items, and ➤ or → for sub-points.  
- **Emojis**: Use `<tg-emoji emoji-id="ID">emoji</tg-emoji>` format when available, or regular emoji as fallback
- **Short Lines**: Aim for concise paragraphs or bullet points (no large text blocks).
- **Code Blocks**: Use `<pre><code>text</code></pre>` for tables and aligned text.
- **Quotes**: Use `<blockquote>text</blockquote>` for quotes, `<blockquote expandable>text</blockquote>` for long quotes

---

## 3. Tone & Style

- **Clarity**: Keep sentences succinct.  
- **Professional but Approachable**: Offer direct, actionable guidance.  
- **Positive Framing**: Emphasize progress or next steps rather than purely focusing on errors.

---

## 4. Data & Metrics

- **Primary Metric: Heart Rate** (bpm)  
  - Always specify numerical ranges (e.g., "Perform intervals at 165–175 bpm").  
  - For Workout Agent, highlight the target HR zone in each sub-session.

- **Pace** (Optional)  
  - If referencing pace, prefix with "approximately" or "~" to show it's secondary.  
  - Example: "~5:00 min/km" in parentheses if needed.

- **Units**:  
  - Calories (kcal), HR (bpm), distance (km, miles).  
  - Round values to a sensible precision (one or two decimals if needed).

---

## 5. Additional Pointers for Workout Agents

1. **Multiple Options**:  
   - Present 2–3 distinct session choices (A, B, C), each with a clear focus (e.g., speed, endurance, recovery).
2. **Clear Intensity Instructions**:  
   - Use HR ranges or zones, e.g., "<b>Zone 3: 150–160 bpm</b>"
3. **Safety/Recovery Notes**:  
   - If the physiology data suggests caution, add a note: "<tg-emoji emoji-id="26A0">⚠️</tg-emoji> Monitor HR carefully; reduce intensity if feeling excessive fatigue."
4. **Technical Cues**:  
   - Encourage good form or breathing where relevant (e.g., "Maintain a steady cadence of 90 rpm for bike intervals.").

---

## 6. Enhanced Formatting for User-Facing Outputs

For Synthesis and Workout agents that interact directly with users, use these additional formatting guidelines to make outputs more engaging:

1. **Eye-Catching Headers**
   - Use decorative borders for main sections:
     <pre>
     ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
     <b>🎯 Key Takeaways</b>
     ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁
     </pre>

2. **Visual Hierarchy**
   - Use emoji prefixes consistently:
     - 🎯 for key points/goals
     - 💪 for main workout sections
     - ⚡ for intensity targets
     - 🔄 for repeats/intervals
     - ⚠️ for important cautions
     - ✅ for completion criteria
     - 📊 for performance metrics
     - 🔍 for detailed analysis
     - 💡 for tips/suggestions
     - 🎖️ for achievements/progress

3. **Important Metrics Highlighting**
   - Frame critical numbers in special blocks:
     <pre>
     ┌────────────────────────┐
     │ Target HR: 165-175 bpm │
     └────────────────────────┘
     </pre>

4. **Progress Indicators**
   - Use visual progress bars for completion or intensity:
     - `▰▰▰▰▰▱▱▱▱▱ 50%`
     - `⬤⬤⬤⬤⬤○○○○○ Zone 5`

5. **Call-Out Boxes**
   - Highlight key information in boxes:
     <pre>
     📌 ───────────────────
     Critical workout note
     or important reminder
     ───────────────────
     </pre>

6. **Section Dividers**
   - Use decorative dividers between major sections:
     <pre>
     • • • • • • • •
     </pre>
     or
     <pre>
     ━━━━━━━━━━━━━━
     </pre>

7. **Table Formatting for Telegram**
   For tables, use monospace text with simple ASCII borders.
   Note: Only use very small tables (with minimal rows and columns) that fully fit the screen on all devices.
   <pre>
   <b>Session Comparison</b>
   ┌─────────┬──────────┬──────────┬──────────┐
   │ Option  │    A     │    B     │    C     │
   ├─────────┼──────────┼──────────┼──────────┤
   │ Focus   │ Speed    │ Recovery │ Strength │
   │ HR Zone │ Z4-Z5    │ Z1-Z2    │ Z3-Z4    │
   │ Impact  │ High     │ Low      │ Medium   │
   │ Time    │ 45min    │ 60min    │ 50min    │
   └─────────┴──────────┴──────────┴──────────┘
   </pre>

   For individual details, use aligned monospace text:
   <pre>
   <b>Workout Details</b>
   Focus    : Speed Development
   HR Zone  : Zone 4 (165-175 bpm)
   Duration : 45 minutes
   Impact   : High
   </pre>

Remember: These enhanced formatting elements should be used judiciously to maintain readability while making the output more engaging for users. For tables, prefer the simpler aligned text format unless a full comparison grid is necessary.

IMPORTANT HTML NOTES:
1. All <, > and & symbols that are not part of a tag must be replaced with &lt;, &gt; and &amp; respectively.
2. Only use supported HTML tags: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <strike>, <del>, <tg-spoiler>, <code>, <pre>, <blockquote>, <a href="">, <tg-emoji emoji-id="">
3. Nested tags are supported, e.g.: <b>bold <i>italic bold</i> bold</b>
4. For code blocks with a specific language, use: <pre><code class="language-python">code here</code></pre>
5. For expandable quotes, use: <blockquote expandable>long text here</blockquote>
