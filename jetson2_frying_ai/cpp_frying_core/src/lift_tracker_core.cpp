#include <cmath>

extern "C" double calc_color_delta(
    double base_h,
    double base_s,
    double base_v,
    double cur_h,
    double cur_s,
    double cur_v
) {
    const double h_diff = std::fmin(std::fabs(base_h - cur_h), 360.0 - std::fabs(base_h - cur_h));
    const double ds = base_s - cur_s;
    const double dv = base_v - cur_v;
    const double delta = std::sqrt((h_diff * 2.0) * (h_diff * 2.0) + ds * ds + dv * dv);
    return delta;
}

extern "C" int check_completion_ready(
    double running_time,
    double target_time,
    double early_sec,
    double color_delta,
    double color_threshold
) {
    const double ready_time = std::fmax(0.0, target_time - early_sec);
    const bool time_ok = running_time >= ready_time;
    const bool color_ok = color_delta >= color_threshold;
    return (time_ok && color_ok) ? 1 : 0;
}
