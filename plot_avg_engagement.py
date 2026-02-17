import os
import glob
import json
import re
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')


def extract_avg_from_file(path):
    name = os.path.basename(path)
    username = None
    avg = None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Skipping {name}: failed to load JSON ({e})")
        return None

    if isinstance(data, dict):
        # try common keys
        for key in ('average_engagement_rate', 'average_engagement_rate_percent', 'average_engagement', 'avg_engagement'):
            if key in data:
                try:
                    avg = float(data[key])
                except:
                    try:
                        avg = float(str(data[key]).strip().replace('%',''))
                    except:
                        avg = None
                break

        # extract username if available
        profile = data.get('profile') if isinstance(data.get('profile'), dict) else None
        if profile:
            username = profile.get('username')

        # fallback: compute average from posts if followers present
        if avg is None and profile and isinstance(data.get('posts'), list):
            followers = profile.get('followers', 0)
            posts = data.get('posts', [])
            if followers and posts:
                total_eng_per_post = 0.0
                count = 0
                for p in posts:
                    likes = p.get('likes', 0) or 0
                    hearts = p.get('hearts', 0) or 0
                    comments = p.get('comments', 0) or 0
                    total_eng_per_post += (likes + hearts + comments)
                    count += 1
                if count > 0:
                    avg = round((total_eng_per_post / count) / followers * 100, 4)

    # final fallback for username: derive from filename
    if not username:
        username = re.sub(r'_data\.json$|\.json$', '', name)

    if avg is None:
        return None

    return username, float(avg)


def main():
    pattern = os.path.join(OUTPUT_DIR, '*.json')
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"No JSON files found in {OUTPUT_DIR}")
        return

    rows = []
    for p in files:
        res = extract_avg_from_file(p)
        if res:
            rows.append(res)

    if not rows:
        print("No average engagement data found in the JSON files.")
        return

    # aggregate by username (take last found if duplicates)
    agg = {}
    for uname, avg in rows:
        agg[uname] = avg

    # sort by avg desc
    items = sorted(agg.items(), key=lambda x: x[1], reverse=True)
    usernames = [i[0] for i in items]
    averages = [i[1] for i in items]

    # plot
    x = np.arange(len(usernames))
    fig, ax = plt.subplots(figsize=(max(8, len(usernames) * 0.4), 6))
    bars = ax.bar(x, averages, color='tab:blue')

    ax.set_xticks(x)
    ax.set_xticklabels(usernames, rotation=45, ha='right')
    ax.set_ylabel('Average Engagement Rate (%)')
    ax.set_title('Average Engagement Rate per Username')

    # label bars
    for rect in bars:
        height = rect.get_height()
        ax.annotate(f'{height:.2f}%', xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords='offset points', ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    out_fname = os.path.join(OUTPUT_DIR, f'avg_engagement_by_user_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
    plt.savefig(out_fname)
    print(f"Chart saved to {out_fname}")


if __name__ == '__main__':
    main()
