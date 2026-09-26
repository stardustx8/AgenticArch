SELECT customer_id,event_id,amount FROM events WHERE status='completed' GROUP BY customer_id ORDER BY customer_id;
