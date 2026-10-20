# Evaluation results

## Sentiment agent vs human labels
Posts: 14485
- **Accuracy: 0.769**
- **Macro F1: 0.735**

Confusion matrix (rows = human label, cols = predicted):

| | negative | neutral | positive |
|---|---|---|---|
| negative | 6981 | 1701 | 400 |
| neutral | 382 | 2068 | 619 |
| positive | 56 | 182 | 2096 |

```
              precision    recall  f1-score   support

    negative      0.941     0.769     0.846      9082
     neutral      0.523     0.674     0.589      3069
    positive      0.673     0.898     0.769      2334

    accuracy                          0.769     14485
   macro avg      0.712     0.780     0.735     14485
weighted avg      0.809     0.769     0.779     14485

```

Per brand accuracy:

- American: 0.782 (n=2604)
- Delta: 0.726 (n=2222)
- Southwest: 0.753 (n=2420)
- US Airways: 0.798 (n=2913)
- United: 0.770 (n=3822)
- Virgin America: 0.800 (n=504)

## Topic clustering vs `negativereason` (United negative posts)
Posts: 1748, clusters found: 20, coverage (not noise): 100.0%
- **Purity: 0.524** (share of each cluster's posts with its majority reason)
- **NMI: 0.222**
- Majority-class baseline purity: 0.306

Largest clusters and their majority human reason:

- cluster 4: 192 posts, majority 'Late Flight' (31%)
- cluster 13: 159 posts, majority 'Lost Luggage' (65%)
- cluster 0: 140 posts, majority 'Bad Flight' (29%)
- cluster 1: 135 posts, majority 'Late Flight' (53%)
- cluster 2: 114 posts, majority 'Customer Service Issue' (65%)
- cluster 7: 93 posts, majority 'Customer Service Issue' (81%)
- cluster 8: 92 posts, majority 'Customer Service Issue' (90%)
- cluster 11: 92 posts, majority 'Late Flight' (50%)
- cluster 3: 89 posts, majority 'Customer Service Issue' (36%)
- cluster 6: 88 posts, majority 'Customer Service Issue' (32%)

## Mention types and emotions (United, no ground truth)

Mention type by source:

```
type_source  mention_type   
rules        Bug Report          140
             Comparison           65
             Complaint          1484
             Feature Request      33
             Other               614
             Praise              715
             Question            771
```

Emotions:

```
emotion
Neutral         1212
Confused         683
Grateful         481
Frustrated       417
Disappointed     401
Delighted        269
Excited          174
Angry             76
Hopeful           39
Surprised         39
Worried           31
```
