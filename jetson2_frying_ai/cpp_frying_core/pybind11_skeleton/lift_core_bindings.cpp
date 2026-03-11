#include <cmath>
#include <pybind11/pybind11.h>

namespace py = pybind11;

double calc_color_delta(
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
    return std::sqrt((h_diff * 2.0) * (h_diff * 2.0) + ds * ds + dv * dv);
}

bool check_completion_ready(
    double running_time,
    double target_time,
    double early_sec,
    double color_delta,
    double color_threshold
) {
    const double ready_time = std::fmax(0.0, target_time - early_sec);
    return (running_time >= ready_time) && (color_delta >= color_threshold);
}

PYBIND11_MODULE(lift_core_pybind, m) {
    m.doc() = "Lift tracker core pybind11 module (skeleton)";
    m.def("calc_color_delta", &calc_color_delta);
    m.def("check_completion_ready", &check_completion_ready);
}
