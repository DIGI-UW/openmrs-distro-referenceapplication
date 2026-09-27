Feature: The daily RHD Patient Flag Refresh
  The RHD Flags module registers "RHD Patient Flag Refresh" on its first start, to run five minutes
  later and then once a day. It re-evaluates every enabled flag, raising the ones that became true
  because time passed, and brings every flag's list in step.

  Scenario: The task is registered and runs daily
    Given I am signed in to the legacy admin UI as "admin"
    When I open Administration, "Manage Scheduler"
    Then I see "RHD Patient Flag Refresh", started, running every 1 days
    When I open it
    Then its class is "org.openmrs.module.rhdflags.task.PatientFlagRefreshTask"
    And it repeats every 86400 seconds and starts on startup

  Scenario: On a new install the first run finds the flags
    Given the stack was started on an empty database
    When five minutes have passed since the RHD Flags module started
    Then the ten RHD lists exist under "System lists", without anyone running the task

  Scenario: Running the task on demand
    When I call, as admin:
      """
      POST /openmrs/ws/rest/v1/taskaction
      {"action": "runtask", "tasks": ["RHD Patient Flag Refresh"]}
      """
    Then the lists reflect the patients' current flags within a few seconds
