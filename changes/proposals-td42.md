patch
- The proposals Action judges with a token that cannot write, and a fixed job checks each build against the
  pipeline's paths before anything is pushed: the pipeline never changes through itself. The queue triages a proposal
  once even when several are filed together. Issues by others are welcome – the owner hands one over with a sealed
  proposal as a comment (`propose-rule`, `propose-feature`) (TD-42, docs/concepts/new/proposals-pipeline.md).
