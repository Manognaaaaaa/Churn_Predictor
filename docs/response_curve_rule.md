Response model for customer *i* in group *g* = (segment, value tier):

`r_i(x) = p_i · v_i · a_g · (1 − exp(−x / τ_i))`, with `τ_i = t_g · v_i`,
`a_g = a · m_seg · m_tier`, `t_g = t · n_seg · n_tier`.

**These parameters are assumptions.** The dataset has no treatment or uplift data (nobody was
randomly offered anything), so how strongly a group responds to an offer cannot be estimated.
Every number is in `configs/config.yaml` under `allocation.response_curves`.

**Rule (written before looking at which strategy wins, not tuned):**

1. *Segment → a.* Engagement index `e_s` = mean of the across-segment z-scores of the segment's
   train-split mean `IsActiveMember` and mean `NumOfProducts`. `m_seg = clip(1 + 0.15·e_s, 0.5, 1.5)`.
   More engaged segments (active members, more products) are assumed to respond more to offers.
2. *Segment → t.* No evidence that segments differ in how large an offer must be, so `n_seg = 1`
   (slope 0).
3. *Tier → t.* Tier index k = −1, 0, +1 for low, mid, high; `n_tier = 1.25^k`. High-value customers
   need a bigger offer to move. Nothing suggests tiers differ in maximum response, so `m_tier = 1`.
4. Defaults `a = 0.30` (the previous global offer uplift) and `t = 0.05` (the previous global
   `tau_frac`).

Caveat: the GMM segments are only weakly separated on engagement (segment means of
`IsActiveMember` range 0.47–0.56 and of `NumOfProducts` 1.28–1.79), so the segment multipliers
are modest by construction. Since `m_tier = n_seg = 1`, tiers affect only `t_g` and segments only `a_g`.
