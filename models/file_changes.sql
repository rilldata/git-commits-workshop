-- Model SQL
-- Reference documentation: https://docs.rilldata.com/build/models
-- @materialize: true
SELECT
    c.time AS time,
    c.hash,
    c.message AS message,
    c.author AS author,
    c.merge AS is_merge_commit,
    c.repo as repo, 
    c.org as org,

    fc.unnest.path AS new_path,
    fc.unnest.path AS file_path,
    SPLIT_PART(fc.unnest.path, '/', -1) AS filename,
    RIGHT(SPLIT_PART(fc.unnest.path, '/', -1), POSITION('.' IN REVERSE(SPLIT_PART(fc.unnest.path, '/', -1)))) AS file_extension,
    CASE WHEN CONTAINS(fc.unnest.path, '/')
      THEN SPLIT_PART(fc.unnest.path, '/', 1)
      ELSE NULL
    END AS first_directory,
    CASE WHEN CONTAINS(SUBSTRING(fc.unnest.path, LENGTH(SPLIT_PART(fc.unnest.path, '/', 1)) + 2), '/')
      THEN SPLIT_PART(fc.unnest.path, '/', 2)
      ELSE NULL
    END AS second_directory,
    CASE
      WHEN CONTAINS(fc.unnest.path, '/') AND CONTAINS(SUBSTRING(fc.unnest.path, LENGTH(SPLIT_PART(fc.unnest.path, '/', 1)) + 2), '/')
        THEN CONCAT(SPLIT_PART(fc.unnest.path, '/', 1), '/', SPLIT_PART(fc.unnest.path, '/', 2))
      WHEN CONTAINS(fc.unnest.path, '/')
        THEN SPLIT_PART(fc.unnest.path, '/', 1)
      ELSE NULL
    END AS second_directory_concat,
    fc.unnest.lines_added AS additions,
    fc.unnest.lines_deleted AS deletions,
    fc.unnest.lines_added + fc.unnest.lines_deleted AS changes,
    fc.unnest.old_path AS previous_file_path
FROM commits c,
unnest(c.file_changes) AS fc