# Rill Workshop Instructions

📊 **Slide Deck**: [View the workshop presentation](https://docs.google.com/presentation/d/1I8TGBGJ_tR1RHqT3VRzmgjfhKpY7LGF0rWMuMdq8Zik/edit?usp=sharing)

### Creating your git commits project

1. Install Rill:
   ```bash
curl https://rill.sh | sh
   
   ```
   Start Rill 
   ```bash
rill start <project_name>
   ```
2. Enable AI Features in Rill Developer (Beta)

Add the following to `rill.yaml`:

```yaml
features: 
  - developerChat
  - generateCanvas
```
3. **Add Data** → Select **Google Cloud Storage** → Skip credentials part (It's a public source)

   Location:
   ```
   gs://rilldata-public/db_repos/commits.json.gz
   ```
4. Wait for data to load (might take 1-2 mins depending on network speed)
5. Generate dashboard using AI 

### Get familiar with core concepts 
Check and review project files one by one
1. `rill.yaml` - project level metadata 
2. `sources/commits.yaml` - source defintion for reading data from GCS to DuckDB 
3. `metrics/commits_metrics.yaml` - Dimensions, measures, security policies
4. `dashboards/commits_explore.yaml` - Exploratory dashboard for commits 
5. `dashboards/commits_canvas.yaml` - Report style canvas dashboard


### Quick Edits using AI as copilot

Add a new dimension commit_uri that points to commits on GitHub
Add a new measure for the number of committers as count distinct authors
Notice the tool calls being made
Explore these new dimensions and measures
Find 1 insight and share it
Popular projects, Top contributors 
Compare activity across projects over time

### Editing code outside of Rill 
Open project in your fav IDE/CLI 
Add a new file models/file_changes.sql 
Copy contents from https://github.com/rilldata/fifthel-workshop/blob/main/models/file_changes.sql
Create a new Metrics View in the same way
https://github.com/rilldata/fifthel-workshop/blob/main/metrics/file_changes_metrics.yaml
Que: What is the lag between adding the file and it reflecting in Rill
BI-as-Code allows any AI-enabled IDE for making changes

### Deploy your project to Rill cloud 
Click on Deploy button top right 
Need signup if have not previously used Rill

### Try conversational BI in rill cloud 
Who are top 10 committers for clickhouse repository in last 3 months
Which commit deleted the most amount of lines? 
Can you spot this commit as anomaly on dashboards ?
Which repository has the highest number of commits in last 1 year ?
Show me number of commits over time

### Further tune AI behavior 
Add business rules additional ai_instructions at project or metrics view level
e.g. My financial year starts on April 1
Fun things to try 
Add ai instruction for AI to respond in hindi or any other language of your choice. (Multi-lingual support)
Ask AI to add respond more funnily 
Ask AI to praise you in every response 
Share the most fun/unexpected response you got :) 


### Connect using MCP server 
https://docs.rilldata.com/explore/mcp
https://www.rilldata.com/blog/top-10-tips-for-using-claude-desktop-with-rill-data

### Advanced Security policies 
https://docs.rilldata.com/build/metrics-view/security



