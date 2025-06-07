# Markdown Style Guide

This guide outlines a consistent Markdown syntax to produce engaging, well-formatted content.

---

## 1. Overall Structure

- **Top-Level Heading**  
  Use Markdown headings (`#`) or bold text for primary titles.  
  **Examples:**  
  ```markdown
  **🏋️‍♂️ Workout Generation - Jan 25, 2025**
  ```
  or
  ```markdown
  # 🏋️‍♂️ Workout Generation - Jan 25, 2025
  ```
  Both approaches create a prominent title.

- **Key Insights / Summary**  
  Begin with a short bullet list summarizing the main points.  
  **Tip:** Use hyphens (`-`) or asterisks (`*`) for bullet points.

- **Main Body**  
  Divide your content into clearly labeled sections using headings (e.g., `### Warm-Up`, `### Main Set`).  
  Use bullet lists for step-by-step instructions.

- **Conclusion / Next Steps**  
  Summarize key action items or recommendations.

- **Spacing**  
  Insert a blank line between major sections and bullet groups to maintain clarity.

---

## 2. Text Formatting Conventions

- **Bold:**  
  Use `**text**` to produce **bold** text.

- **Italic:**  
  Use `*text*` or `_text_` to produce *italic* text.

- **Underline:**  
  Use double underscores (`__text__`) to produce <u>underline</u>.

- **Strikethrough:**  
  Use `~~text~~` to produce ~~strikethrough~~ text.

- **Inline Code:**  
  Wrap text in backticks: `` `code` `` produces inline code formatting.

- **Code Blocks:**  
  Use triple backticks with an optional language specifier:
  ```markdown
  ```python
  print("Hello, world!")
  ```
  ```
  This produces a nicely formatted code block.

- **Links:**  
  Use `[text](URL)` to create hyperlinks.

- **Images:**  
  Use `![Alt text](URL)` to include images. For concise outputs, you may also link images as:  
  ```markdown
  [Alt text](URL)
  ```

- **Blockquotes:**  
  Start a line with `>` for blockquotes.
  ```markdown
  > This is a blockquote.
  ```

---

## 3. Headings and Lists

- **Headings:**  
  Lines beginning with one or more `#` create headings, which are typically rendered as bold text.
  ```markdown
  # Heading 1
  ## Heading 2
  ```

- **Bullet Lists:**  
  Lines starting with `-` or `*` become bullet points.
  ```markdown
  - Item one
  * Item two
  ```
  These are often rendered with a bullet (e.g., `•`) prefix.

- **Ordered Lists:**  
  Numbers followed by a period create ordered lists with preserved numbering.

---

## 4. Advanced Formatting

- **Nested Formatting:**  
  Nested markdown is supported. For example:
  ```markdown
  **This is bold and *italic* text**
  ```
  renders as bold text with an italicized section inside.

  You can also mix underline with bold:
  ```markdown
  **Bold and __underline__**
  ```
  which displays as bold text with an underlined portion.

- **Inline Code Within Formatted Text:**  
  Inline code can appear within bold or italic text:
  ```markdown
  **Bold with `inline code` inside**
  ```
  This will correctly format the inline code within the bold text.

- **Tables:**  
  Use tables sparingly and only for very small datasets, as display sizes vary.  
  **Example:**
  ```markdown
  **Session Comparison**
  ┌─────────┬──────────┬──────────┐
  │ Option  │    A     │    B     │
  ├─────────┼──────────┼──────────┤
  │ Focus   │ Speed    │ Recovery │
  │ HR Zone │ Z4-Z5    │ Z1-Z2    │
  │ Time    │ 45min    │ 60min    │
  └─────────┴──────────┴──────────┘
  ```
  Keep such tables concise.

---

## 5. Enhanced Visual Hierarchy

- **Eye-Catching Headers:**  
  Use decorative borders to highlight main sections.  
  **Example:**
  ```markdown
  ----------------------------
  **🎯 Key Takeaways**
  ----------------------------
  ```

- **Emoji Prefixes:**  
  Enhance your content by using emojis consistently:
  - 🎯 for key points or goals  
  - 💪 for main workout sections  
  - ⚡ for intensity targets  
  - 🔄 for intervals or repeats  
  - ⚠️ for cautions  
  - ✅ for completion criteria  
  - 📊 for performance metrics  
  - 🔍 for detailed analysis  
  - 💡 for tips or suggestions  
  - 🎖️ for achievements or progress

- **Important Metrics Highlighting:**  
  Frame critical numbers in a special block to draw attention:
  ```markdown
  ┌────────────────────────┐
  │ Target HR: 165-175 bpm │
  └────────────────────────┘
  ```

- **Progress Indicators:**  
  Use visual progress bars to show completion or intensity:
  ```markdown
  ▰▰▰▰▰▱▱▱▱▱ 50%
  ⬤⬤⬤⬤⬤○○○○○ Zone 5
  ```

- **Call-Out Boxes:**  
  Highlight important notes or reminders with call-out boxes:
  ```markdown
  📌 -------------------
  Critical workout note or important reminder
  -------------------
  ```

- **Section Dividers:**  
  Separate major sections with dividers:
  ```markdown
  • • • • • • • •
  ```
  or
  ```markdown
  ━━━━━━━━━━━━━━
  ```

---

## 6. Best Practices

- **Consistency:**  
  Always use balanced delimiters for Markdown elements. Close all inline code and code blocks properly.

- **Clarity:**  
  Write concise paragraphs and bullet points. Use headings and spacing to improve readability.

- **Testing:**  
  Regularly review your Markdown output to ensure that all elements display correctly across different devices and font sizes.

---

Happy formatting!