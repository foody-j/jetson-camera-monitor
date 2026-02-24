#include <algorithm>
#include <cctype>
#include <cmath>
#include <sstream>
#include <string>
#include <vector>

namespace {

int clamp_int(int v, int lo, int hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

std::string to_lower_copy(const std::string& s) {
    std::string out = s;
    std::transform(out.begin(), out.end(), out.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return out;
}

bool is_in_class(const std::string& name) {
    const std::string lower = to_lower_copy(name);
    return lower == "in" || (lower.find("in") != std::string::npos);
}

std::vector<std::string> split_csv(const std::string& csv) {
    std::vector<std::string> out;
    std::stringstream ss(csv);
    std::string item;
    while (std::getline(ss, item, ',')) {
        out.push_back(item);
    }
    return out;
}

}  // namespace

extern "C" int select_inner_box(
    const float* boxes_xyxy,
    const float* confs,
    const int* cls_ids,
    int num_boxes,
    const char* class_names_csv,
    int cam_id,
    int right_cam_id,
    float right_min_ratio,
    int frame_w,
    int frame_h,
    int bbox_pad,
    float inner_margin,
    int* out_has_box,
    int* out_x1,
    int* out_y1,
    int* out_x2,
    int* out_y2,
    int* out_ix1,
    int* out_iy1,
    int* out_ix2,
    int* out_iy2
) {
    if (!boxes_xyxy || !confs || !cls_ids || !class_names_csv || !out_has_box ||
        !out_x1 || !out_y1 || !out_x2 || !out_y2 || !out_ix1 || !out_iy1 || !out_ix2 || !out_iy2) {
        return -1;
    }
    if (num_boxes <= 0 || frame_w <= 1 || frame_h <= 1) {
        *out_has_box = 0;
        return 0;
    }

    const std::vector<std::string> names = split_csv(class_names_csv);
    std::vector<int> in_indices;
    in_indices.reserve(static_cast<size_t>(num_boxes));

    for (int i = 0; i < num_boxes; ++i) {
        const int cls = cls_ids[i];
        if (cls < 0 || cls >= static_cast<int>(names.size())) {
            continue;
        }
        if (is_in_class(names[cls])) {
            in_indices.push_back(i);
        }
    }

    if (in_indices.empty()) {
        *out_has_box = 0;
        return 0;
    }

    int best_idx = -1;
    if (cam_id == right_cam_id) {
        right_min_ratio = std::max(0.0f, std::min(1.0f, right_min_ratio));
        const float split_x = static_cast<float>(frame_w) * right_min_ratio;
        std::vector<int> right_indices;
        right_indices.reserve(in_indices.size());
        for (int idx : in_indices) {
            const float x1 = boxes_xyxy[idx * 4 + 0];
            const float x2 = boxes_xyxy[idx * 4 + 2];
            const float cx = (x1 + x2) * 0.5f;
            if (cx >= split_x) {
                right_indices.push_back(idx);
            }
        }
        if (right_indices.empty()) {
            *out_has_box = 0;
            return 0;
        }
        best_idx = right_indices[0];
        for (int idx : right_indices) {
            const float cur_x1 = boxes_xyxy[idx * 4 + 0];
            const float best_x1 = boxes_xyxy[best_idx * 4 + 0];
            if (cur_x1 > best_x1) {
                best_idx = idx;
            }
        }
    } else {
        best_idx = in_indices[0];
        for (int idx : in_indices) {
            if (confs[idx] > confs[best_idx]) {
                best_idx = idx;
            }
        }
    }

    int x1 = clamp_int(static_cast<int>(std::lround(boxes_xyxy[best_idx * 4 + 0])) - bbox_pad, 0, frame_w - 1);
    int y1 = clamp_int(static_cast<int>(std::lround(boxes_xyxy[best_idx * 4 + 1])) - bbox_pad, 0, frame_h - 1);
    int x2 = clamp_int(static_cast<int>(std::lround(boxes_xyxy[best_idx * 4 + 2])) + bbox_pad, 0, frame_w - 1);
    int y2 = clamp_int(static_cast<int>(std::lround(boxes_xyxy[best_idx * 4 + 3])) + bbox_pad, 0, frame_h - 1);

    const int bw = x2 - x1;
    const int bh = y2 - y1;
    const int mx = static_cast<int>(bw * inner_margin);
    const int my = static_cast<int>(bh * inner_margin);
    const int ix1 = clamp_int(x1 + mx, 0, frame_w - 1);
    const int iy1 = clamp_int(y1 + my, 0, frame_h - 1);
    const int ix2 = clamp_int(x2 - mx, 0, frame_w - 1);
    const int iy2 = clamp_int(y2 - my, 0, frame_h - 1);

    if (ix2 <= ix1 || iy2 <= iy1) {
        *out_has_box = 0;
        return 0;
    }

    *out_has_box = 1;
    *out_x1 = x1;
    *out_y1 = y1;
    *out_x2 = x2;
    *out_y2 = y2;
    *out_ix1 = ix1;
    *out_iy1 = iy1;
    *out_ix2 = ix2;
    *out_iy2 = iy2;
    return 0;
}
