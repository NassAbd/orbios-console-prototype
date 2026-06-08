#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "payload.h"
#define BUFFER_SIZE 4096
#include <unistd.h>
#include <time.h>

// Fonction utilitaire à ajouter en haut du fichier
double get_time_ms() {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}
/* ---------- SATELLITE OS PART ---------- */
int copy_file(const char *src_path, const char *dst_path) {
    FILE *src = fopen(src_path, "rb");
    if(!src) {
        printf("[OS] ERROR opening source file\n");
        return 1;
    }
    FILE *dst = fopen(dst_path, "wb");
    if(!dst) {
        printf("[OS] ERROR opening destination file\n");
        fclose(src);
        return 1;
    }
    char buffer[BUFFER_SIZE];
    size_t bytes_read;
    while((bytes_read = fread(buffer, 1, BUFFER_SIZE, src)) > 0) {
        fwrite(buffer, 1, bytes_read, dst);
    }
    fclose(src);
    fclose(dst);
    printf("[OS] File transferred successfully\n");
    return 0;
}

/* ---------- OUTPUT ALERT FILE ---------- */
void create_output_file(SensorData data, int alert_type) {
    char filename[256];
    if(alert_type == 1) {
        sprintf(
            filename,
            "output/WILDFIRE_LAT%.3f_LON%.3f.dat",
            data.lat,
            data.lon
        );
    } else {
        sprintf(
            filename,
            "output/FALSE_ALERT_LAT%.3f_LON%.3f.dat",
            data.lat,
            data.lon
        );
    }
    // create empty 0-byte file
    FILE *f = fopen(filename, "w");
    if(f != NULL)
        fclose(f);
    printf("[PAYLOAD] Created: %s\n", filename);
}

/* ---------- PAYLOAD DETECTION ---------- */
void run_wildfire_detection() {
    printf("\n[PAYLOAD] Starting wildfire detection...\n\n");
    FILE *file = fopen("input.csv", "r");
    if(file == NULL) {
        printf("Error opening CSV file\n");
        return;
    }
    char line[1024];
    char *token;
    int i;
    fgets(line, sizeof(line), file);
    while(fgets(line, sizeof(line), file)) {
        SensorData data;
        data.lat = 0;
        data.lon = 0;
        data.time = 0;
        data.brightness = 0;
        data.frp = 0;
        data.confidence = 'l';
        i = 0;
        token = strtok(line, ",;");
        while(token != NULL) {
            token[strcspn(token, "\n")] = 0;
            if(i == 0)
                data.lat = atof(token);
            else if(i == 1)
                data.lon = atof(token);
            else if(i == 2)
                data.time = atoi(token);
            else if(i == 3)
                data.brightness = atof(token);
            else if(i == 9)
                data.confidence = token[0];
            else if(i == 12)
                data.frp = atof(token);
            token = strtok(NULL, ",;");
            i++;
        }
        float score = compute_risk_score(data);
        printf(
            "[PAYLOAD] Brightness=%.2f FRP=%.2f CONF=%c SCORE=%.2f\n",
            data.brightness,
            data.frp,
            data.confidence,
            score
        );
        int alert = generate_alert(data, score);
        create_output_file(data, alert);
        sleep(3);
    }
    fclose(file);
    printf("\n[PAYLOAD] Detection completed\n");
}

/* ---------- MAIN ---------- */
int main() {
    printf("[OS] Satellite OS running normally...\n\n");
    double t0, t1;
    // --- PRE-PROCESSING: NAVIGATION & ATTITUDE FILES ---
    t0 = get_time_ms();
    copy_file("call1/Ephemeris_signal_reception.dat",       "output/Ephemeris_signal_reception.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3); // attend 3 secondes avant le prochain transfert
    t0 = get_time_ms();
    copy_file("call1/Real_time_position_tracking.dat",      "output/Real_time_position_tracking.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Onboard_clock_synchronization.dat",    "output/Onboard_clock_synchronization.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Star_tracker_attitude_extraction.dat", "output/Star_tracker_attitude_extraction.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/AOCS_filter_recalculation.dat",        "output/AOCS_filter_recalculation.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Trajectory_propagation_verification.dat", "output/Trajectory_propagation_verification.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Nominal_state_maintenance.dat",        "output/Nominal_state_maintenance.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    printf("\n[OS] Pre-processing files transferred\n");

    // --- PAYLOAD PROCESSING: INPUT -> OUTPUT ---
    run_wildfire_detection();


    // --- POST-PROCESSING: RETARGETING & MANEUVER FILES ---
    t0 = get_time_ms();
    copy_file("call1/Sensors_retargeting.dat",                  "output/Sensors_retargeting.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Attitude_acquisition.dat",                 "output/Attitude_acquisition.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Guidance_calculation.dat",                 "output/Guidance_calculation.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Target_setpoint_calculation.dat",          "output/Target_setpoint_calculation.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Previous_pointing_mode_deactivation.dat",  "output/Previous_pointing_mode_deactivation.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Actuator_commanding.dat",                  "output/Actuator_commanding.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Controlled_deceleration.dat",              "output/Controlled_deceleration.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Target_acquisition.dat",                   "output/Target_acquisition.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Attitude_settling.dat",                    "output/Attitude_settling.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/Nominal_mode_restoration.dat",             "output/Nominal_mode_restoration.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);
    t0 = get_time_ms();
    copy_file("call1/OIL_LEAK_LAT41.122_LON-8.895.dat",        "output/OIL_LEAK_LAT41.122_LON-8.895.dat");
    t1 = get_time_ms();
    printf("[OS] Delta: %.2f ms\n\n", t1 - t0);
    sleep(3);

    printf("\n[OS] Post-processing files transferred\n");
    printf("\n[OS] Pipeline completed successfully\n");
    return 0;
}