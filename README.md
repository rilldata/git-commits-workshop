# Rill Workshop Instructions

📊 **Slide Deck**: [View the workshop presentation](https://docs.google.com/presentation/d/1I8TGBGJ_tR1RHqT3VRzmgjfhKpY7LGF0rWMuMdq8Zik/edit?usp=sharing)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](../../codespaces/new?hide_repo_select=true)

### Creating your git commits project

1. Install Rill:
   ```bash
   curl https://rill.sh | sh
   ```
   
   Start Rill:
   ```bash
   rill start rill-git-analytics
   ```

2. Rill opens in your browser. Click on **Start with an empty project** 

3. Enable AI Features in Rill Developer (Beta)
   
   Add the following to `rill.yaml`:

    ```yaml
    features: 
        developerChat: true
        generateCanvas: true
    ```

4. **Add -> Data** (Top left) → Select **Google Cloud Storage** → Skip credentials part (It's a public source)
   
   Location:
   ```
   gs://rilldata-public/db_repos/commits.json.gz
   ```
4. Wait for data to load (might take 1-2 mins depending on network speed)
5. Generate dashboard using AI 

### Get familiar with core concepts

Check and review project files one by one:

1. **Project Metadata** ([`rill.yaml`](./rill.yaml)) - project level metadata
2. **Sources** ([`sources/commits.yaml`](./sources/commits.yaml)) - source definition for reading data from GCS to DuckDB
3. **Metrics View** ([`metrics/commits_metrics.yaml`](./metrics/commits_metrics.yaml)) - Dimensions, measures, security policies
4. **Explore** ([`dashboards/commits_metrics_explore.yaml`](./dashboards/commits_metrics_explore.yaml)) - Exploratory dashboard for commits
5. **Canvas** ([`dashboards/commits_metrics_canvas.yaml`](./dashboards/commits_metrics_canvas.yaml)) - Report style canvas dashboard


### Quick Edits using AI as copilot
Use prompt below - 
```
Add a new dimension `commit_uri` that points to commits on GitHub
Add a new measure for the number of committers as count distinct authors
```
1. Notice the tool calls being made
2. Explore these new dimensions and measures
3. Find 1 insight and share it
4. Popular projects, Top contributors
5. Compare activity across projects over time

### Editing code outside of Rill

1. Open project in your fav IDE/CLI
2. Add a new file [`models/file_changes.sql`](./models/file_changes.sql)
3. Copy contents from [file_changes.sql](https://github.com/rilldata/fifthel-workshop/blob/main/models/file_changes.sql)
4. Create a new Metrics View in the same way
5. [file_changes_metrics.yaml](./metrics/file_changes_metrics.yaml)
6. Que: What is the lag between adding the file and it reflecting in Rill
7. BI-as-Code allows any AI-enabled IDE for making changes

### Deploy your project to Rill cloud

1. Click on Deploy button top right
2. Need signup if have not previously used Rill

### Try conversational BI in rill cloud

1. Who are top 10 committers for clickhouse repository in last 3 months
2. Which commit deleted the most amount of lines?
3. Can you spot this commit as anomaly on dashboards?
4. Which repository has the highest number of commits in last 1 year?
5. Show me number of commits over time

### Further tune AI behavior by adding more business context

1. Add business rules additional ai_instructions at project or metrics view level
2. e.g. My financial year starts on April 1
3. Refer to [AI Configuration documentation](https://docs.rilldata.com/build/ai-configuration)

**Fun things to try**:

1. Add ai instruction for AI to respond in hindi or any other language of your choice. (Multi-lingual support)
2. Ask AI to add respond more funnily
3. Ask AI to praise you in every response
4. Add thanking notes 
5. Share the most fun/unexpected response you got :) 

## Further exploration

**Your own git commits data**

- Use script in [`scripts/extract_commits.py`](./scripts/extract_commits.py) to extract commits from one or more repositories

**Connect using MCP server**

- [MCP Server Documentation](https://docs.rilldata.com/explore/mcp)
- [Top 10 Tips for Using Claude Desktop with Rill Data](https://www.rilldata.com/blog/top-10-tips-for-using-claude-desktop-with-rill-data)

**Advanced Security policies**

- [Security Policies Documentation](https://docs.rilldata.com/build/metrics-view/security)

**Embedding Rill in your applications**

- [Embedding Documentation](https://docs.rilldata.com/integrate/embedding)


### More demo projects

1. Check out public [Rill Demo Projects](https://ui.rilldata.com/demo)
2. [Example projects on GitHub](https://github.com/rilldata/rill-examples)

---

### Get Involved

1. Like & Star the [Rill project on GitHub](https://github.com/rilldata/rill) if you found it useful
2. For any questions reach on [Discord](https://discord.gg/2ubRfjC7Rh) or report issues
3. If you are building something similar, let's connect, collaborate and share ideas



