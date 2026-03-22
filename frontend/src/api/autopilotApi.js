import { apiClient } from "./client";

export const fetchAutopilotStatus = async (tripId) => {
  const { data } = await apiClient.get(`/autopilot/status/${tripId}`);
  return data;
};

export const triggerAutopilot = async (tripId) => {
  const { data } = await apiClient.post(`/autopilot/trigger/${tripId}`);
  return data;
};
