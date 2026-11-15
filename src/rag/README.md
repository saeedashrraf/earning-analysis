# Part 1: RAG

**Problem:** LLMs invent facts. Every answer must point to the exact place in the filing it came from, so it can be checked.

## How it works

```
1. Load      download the annual report
     │
2. Parse     HTML → clean text, with section labels
     │
3. Chunk     split text into small passages
     │
4. Embed     turn each passage into a vector
     │
5. Retrieve  find the passages closest to a question
     │
6. Answer    LLM writes the answer, citing its passages
```

The section labels from step 2 are what make the citations in step 6 possible.

## Progress

- [x] 1. Load — done by the [report downloader](../report_downloader/)
- [ ] 2. Parse ← next
- [ ] 3. Chunk
- [ ] 4. Embed
- [ ] 5. Retrieve
- [ ] 6. Answer

## Class structure

To be written as we build.

## Components

To be written as we build.
