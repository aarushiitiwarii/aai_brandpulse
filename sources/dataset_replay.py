"""Loads the real Twitter US Airline Sentiment dataset and replays it by timestamp."""
import re

import pandas as pd

from core import db
from core.config import RAW_CSV

TIME_FMT = "%Y-%m-%d %H:%M:%S"

# The Kaggle export replaced the words "late"/"cancelled" with label text; undo it for display/NLP.
_ARTIFACTS = [
    (re.compile(r"Cancelled Flightled", re.I), "cancelled"),
    (re.compile(r"Cancelled Flighted", re.I), "cancelled"),
    (re.compile(r"Cancelled Flight", re.I), "cancel"),
    (re.compile(r"Late Flightr", re.I), "later"),
    (re.compile(r"Late Flight", re.I), "late"),
]


def clean_text(text: str) -> str:
    for pat, rep in _ARTIFACTS:
        text = pat.sub(rep, text)
    return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def load_tweets(path=RAW_CSV) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Download Tweets.csv from "
            "https://www.kaggle.com/datasets/crowdflower/twitter-airline-sentiment "
            "and put it in data/raw/."
        )
    df = pd.read_csv(path)
    created = pd.to_datetime(df["tweet_created"], format="%Y-%m-%d %H:%M:%S %z", utc=True)
    out = pd.DataFrame({
        "id": df["tweet_id"].astype(str),
        "source": "twitter",
        "brand": df["airline"],
        "handle": "@" + df["name"].astype(str),
        "text": df["text"].astype(str).map(clean_text),
        # all tweets are Pacific time (-0800); keep local wall-clock time as sortable text
        "created_at": created.dt.tz_convert("Etc/GMT+8").dt.strftime(TIME_FMT),
        "retweet_count": df["retweet_count"].fillna(0).astype(int),
        "location": df["tweet_location"].fillna(""),
        "is_synthetic": 0,
        "label_sentiment": df["airline_sentiment"],
        "label_reason": df["negativereason"].fillna(""),
    })
    return out.drop_duplicates("id").sort_values("created_at").reset_index(drop=True)


def time_bounds():
    df = db.query_df("SELECT MIN(created_at) AS lo, MAX(created_at) AS hi FROM posts WHERE is_synthetic=0 AND is_live=0")
    return df.loc[0, "lo"], df.loc[0, "hi"]


def shift(ts: str, minutes: float) -> str:
    return (pd.Timestamp(ts) + pd.Timedelta(minutes=minutes)).strftime(TIME_FMT)
