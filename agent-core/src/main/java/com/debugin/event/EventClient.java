package com.debugin.event;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.OutputStream;
import java.util.Map;
import java.util.logging.Logger;
import java.util.logging.Level;

/**
 * HTTP client for sending canonical events to the event sink.
 * POSTs events to /api/events with bounded retry behavior.
 */
public class EventClient {
    private static final Logger logger = Logger.getLogger(EventClient.class.getName());
    private static final int CONNECT_TIMEOUT_MS = 5000;
    private static final int READ_TIMEOUT_MS = 5000;
    private static final int MAX_RETRIES = 3;

    private final String sinkUrl;
    private final ObjectMapper objectMapper;

    public EventClient(String sinkUrl) {
        this.sinkUrl = sinkUrl;
        this.objectMapper = new ObjectMapper();
    }

    /**
     * Send an event to the event sink
     */
    public boolean send(Map<String, Object> event) {
        if (sinkUrl == null || sinkUrl.isEmpty()) {
            logger.warning("Event sink URL not configured");
            return false;
        }

        int retries = 0;
        long backoffMs = 100;

        while (retries < MAX_RETRIES) {
            try {
                return sendWithRetry(event);
            } catch (Exception e) {
                retries++;
                if (retries < MAX_RETRIES) {
                    logger.log(Level.INFO, "Event send failed, retry " + retries + "/" + MAX_RETRIES, e);
                    try {
                        Thread.sleep(backoffMs);
                        backoffMs *= 2;  // Exponential backoff
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        return false;
                    }
                } else {
                    logger.log(Level.WARNING, "Failed to send event after " + MAX_RETRIES + " retries", e);
                    return false;
                }
            }
        }
        return false;
    }

    private boolean sendWithRetry(Map<String, Object> event) throws Exception {
        String endpoint = sinkUrl.endsWith("/") ? sinkUrl + "api/events" : sinkUrl + "/api/events";
        URL url = new URL(endpoint);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();

        try {
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setConnectTimeout(CONNECT_TIMEOUT_MS);
            conn.setReadTimeout(READ_TIMEOUT_MS);
            conn.setDoOutput(true);

            // Serialize and send event
            String jsonEvent = objectMapper.writeValueAsString(event);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(jsonEvent.getBytes("UTF-8"));
                os.flush();
            }

            int responseCode = conn.getResponseCode();
            if (responseCode >= 200 && responseCode < 300) {
                logger.fine("Event sent successfully: " + responseCode);
                return true;
            } else if (responseCode >= 400 && responseCode < 500) {
                logger.warning("Client error sending event: " + responseCode);
                return false;
            } else if (responseCode >= 500) {
                logger.warning("Server error sending event: " + responseCode);
                throw new RuntimeException("Server error: " + responseCode);
            }
            return false;
        } finally {
            conn.disconnect();
        }
    }
}
