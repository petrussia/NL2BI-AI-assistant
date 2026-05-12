WITH job_applications AS (
    SELECT 
        a.id AS application_id,
        a.candidate_id,
        a.created_at AS application_created_at,
        o.id AS opportunity_id,
        o.name AS opportunity_name,
        p.id AS posting_id,
        p.text AS posting_text
    FROM 
        {{ ref('lever__application') }} a
    JOIN 
        {{ ref('lever__opportunity') }} o ON a.opportunity_id = o.id
    JOIN 
        {{ ref('lever__posting') }} p ON o.requisition_code = p.requisition_code
),

job_interviews AS (
    SELECT 
        i.id AS interview_id,
        i.candidate_id,
        i.date AS interview_date,
        i.location AS interview_location,
        i.subject AS interview_subject,
        o.id AS opportunity_id,
        o.name AS opportunity_name,
        p.id AS posting_id,
        p.text AS posting_text
    FROM 
        {{ ref('lever__interview') }} i
    JOIN 
        {{ ref('lever__opportunity') }} o ON i.opportunity_id = o.id
    JOIN 
        {{ ref('lever__posting') }} p ON o.requisition_code = p.requisition_code
),

job_requisitions AS (
    SELECT 
        r.id AS requisition_id,
        r.job_title,
        r.job_location,
        r.status,
        r.owner_user_id,
        u.name AS owner_name
    FROM 
        {{ ref('lever__requisition_enhanced') }} r
    LEFT JOIN 
        {{ ref('lever__user') }} u ON r.owner_user_id = u.id
),

job_tags AS (
    SELECT 
        ot.opportunity_id,
        ot.tag
    FROM 
        {{ ref('lever__opportunity_tag') }} ot
),

job_hiring_managers AS (
    SELECT 
        u.id AS user_id,
        u.name AS name,
        u.email AS email
    FROM 
        {{ ref('lever__user') }} u
    WHERE 
        u.role = 'Hiring Manager'
)

SELECT 
    j.id AS job_id,
    j.job_title,
    j.job_location,
    j.status,
    j.owner_name,
    j.tags,
    j.applications_count,
    j.interviews_count,
    j.hiring_managers
FROM (
    SELECT 
        r.id AS job_id,
        r.job_title,
        r.job_location,
        r.status,
        r.owner_name,
        STRING_AGG(DISTINCT t.tag, ', ') AS tags,
        COUNT(a.id) AS applications_count,
        COUNT(i.id) AS interviews_count,
        ARRAY_AGG(DISTINCT hm.name ORDER BY hm.name) AS hiring_managers
    FROM 
        job_requisitions r
    LEFT JOIN 
        job_tags t ON r.id = t.opportunity_id
    LEFT JOIN 
        job_applications a ON r.id = a.opportunity_id
    LEFT JOIN 
        job_interviews i ON r.id = i.opportunity_id
    LEFT JOIN 
        job_hiring_managers hm ON r.owner_user_id = hm.user_id
    GROUP BY 
        r.id, r.job_title, r.job_location, r.status, r.owner_name
) j;
