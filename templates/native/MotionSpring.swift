// MotionSpring.swift: ui-motion template. Copy into the app target; name the spec it implements here.
// A port of templates/motion-runtime.js: closed-form springs and exact-endpoint easings, so the
// SwiftUI build produces the same values at the same t as the reviewed seek(t) page.
import Foundation

/// Easing function on 0…1 with exact 0 and 1 at the ends.
struct Ease {
    let f: (Double) -> Double
    func callAsFunction(_ p: Double) -> Double { p <= 0 ? 0 : (p >= 1 ? 1 : f(p)) }

    static func cubicBezier(_ x1: Double, _ y1: Double, _ x2: Double, _ y2: Double) -> Ease {
        func bx(_ s: Double) -> Double { 3 * x1 * s * (1 - s) * (1 - s) + 3 * x2 * s * s * (1 - s) + s * s * s }
        func by(_ s: Double) -> Double { 3 * y1 * s * (1 - s) * (1 - s) + 3 * y2 * s * s * (1 - s) + s * s * s }
        func dx(_ s: Double) -> Double { 3 * x1 * (1 - s) * (1 - s) + 6 * (x2 - x1) * s * (1 - s) + 3 * (1 - x2) * s * s }
        return Ease { x in
            var s = x
            for _ in 0..<8 {
                let err = bx(s) - x
                if abs(err) < 1e-7 { return by(s) }
                let d = dx(s)
                if abs(d) < 1e-6 { break }
                s -= err / d
            }
            var lo = 0.0, hi = 1.0
            s = x
            for _ in 0..<40 {
                let v = bx(s)
                if abs(v - x) < 1e-7 { break }
                if v < x { lo = s } else { hi = s }
                s = (lo + hi) / 2
            }
            return by(s)
        }
    }

    static let linear = Ease { $0 }
    static let standard = cubicBezier(0.2, 0, 0, 1)
    static let out = cubicBezier(0.16, 1, 0.3, 1)
    static let outQuart = cubicBezier(0.25, 1, 0.5, 1)
    static let `in` = cubicBezier(0.55, 0, 1, 0.45)
    static let inOut = cubicBezier(0.65, 0, 0.35, 1)
}

/// Closed-form damped spring from 0 to 1 (mass-spring-damper), identical to motion-runtime.js.
struct MotionSpring {
    let stiffness: Double, damping: Double, mass: Double, velocity: Double
    let omega: Double, zeta: Double
    private(set) var settle: Double = 0

    init(stiffness: Double, damping: Double, mass: Double = 1, velocity: Double = 0) {
        self.stiffness = stiffness; self.damping = damping; self.mass = mass; self.velocity = velocity
        omega = (stiffness / mass).squareRoot()
        zeta = damping / (2 * (stiffness * mass).squareRoot())
        // Settle: last time |x - 1| or |v| / ω0 exceeds 0.1% of travel, scanned at 1 ms.
        var last = 0.0
        var t = 0.0
        while t < 10 {
            if abs(position(t) - 1) > 0.001 || abs(rawVelocity(t)) / max(omega, 1) > 0.001 { last = t }
            t += 0.001
        }
        settle = ((last + 0.001) * 1000).rounded() / 1000
    }

    func callAsFunction(_ t: Double) -> Double { t <= 0 ? 0 : (t >= settle ? 1 : position(t)) }

    private func position(_ t: Double) -> Double {
        let v0 = velocity, z = zeta, w0 = omega
        if z < 1 - 1e-9 {
            let wd = w0 * (1 - z * z).squareRoot()
            let a = -1.0, b = (v0 + z * w0 * a) / wd
            return 1 + exp(-z * w0 * t) * (a * cos(wd * t) + b * sin(wd * t))
        } else if z <= 1 + 1e-9 {
            let a = -1.0, b = v0 + w0 * a
            return 1 + (a + b * t) * exp(-w0 * t)
        } else {
            let sq = (z * z - 1).squareRoot()
            let r1 = -w0 * (z - sq), r2 = -w0 * (z + sq)
            let c2 = (v0 + r1) / (r2 - r1), c1 = -1 - c2
            return 1 + c1 * exp(r1 * t) + c2 * exp(r2 * t)
        }
    }

    private func rawVelocity(_ t: Double) -> Double {
        let h = 1e-5
        return (position(t + h) - position(t - h)) / (2 * h)
    }
}

@inline(__always) func mix(_ a: Double, _ b: Double, _ p: Double) -> Double { a + (b - a) * p }
@inline(__always) func clamp01(_ v: Double) -> Double { min(1, max(0, v)) }
func progress(_ t: Double, _ start: Double, _ dur: Double) -> Double { dur <= 0 ? (t >= start ? 1 : 0) : clamp01((t - start) / dur) }
func tween(_ t: Double, _ start: Double, _ dur: Double, _ from: Double, _ to: Double, _ ease: Ease = .standard) -> Double {
    mix(from, to, ease(progress(t, start, dur)))
}
/// keyframes(t, [(time, value, easeIntoThisKey)]): holds first/last value outside the keys.
func keyframes(_ t: Double, _ keys: [(Double, Double, Ease)]) -> Double {
    guard let first = keys.first, let last = keys.last else { return 0 }
    if t <= first.0 { return first.1 }
    for i in 1..<keys.count where t <= keys[i].0 {
        let a = keys[i - 1], b = keys[i]
        return mix(a.1, b.1, b.2(progress(t, a.0, b.0 - a.0)))
    }
    return last.1
}
