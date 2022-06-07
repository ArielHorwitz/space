from loguru import logger
import math
import numpy as np

from logic import EPSILON
from logic._3d import RADIANS_IN_DEGREES, GOOGOL


class Quaternion:
    @classmethod
    def rotate_vectors(cls, vectors, q):
        """Rotate 3d vectors using a quaternion of rotation. Returns rotated 3d vectors."""
        assert len(vectors.shape) == 2
        assert vectors.shape[1] == 3
        assert q.shape == (4, )
        z = np.zeros((*vectors.shape[:-1], 1), dtype=np.float64)
        vector_quats = np.concatenate((z, vectors), axis=-1)
        r = cls.rotate_quaternions(vector_quats, q)[:, 1:]
        return r

    @classmethod
    def rotate_quaternions(cls, p, q):
        """Rotate 4d quaternions p using a 4d quaternion of rotation q. Returns rotated 4d quaternions."""
        assert len(p.shape) == 2
        assert p.shape[1] == 4
        assert q.shape == (4, )
        qp = cls.multiply_one_many(q, p)
        p_ = cls.multiply_many_one(qp, cls.inverse(q))
        return p_

    @classmethod
    def rotate_about_axis(cls, v, rotation_axis_vector, rotation_angle_degrees):
        """Rotate 3d vector about a given axis by a given angle. Returns rotated 3d vector."""
        assert v.shape == (3, )
        # p = quaternion of self: the point/vector to rotate
        p = cls.from_vector(v)
        # q = the quaternion of rotation
        q = cls.give_quaternion_of_rotation(rotation_axis_vector, rotation_angle_degrees)
        # rotate the quaternion (q * p * q_)
        p_ = cls.rotate_quaternion(p, q)
        # return the rotated 3d vector of resulting quaternion
        return p_[1:]

    @classmethod
    def rotate_vector(cls, v, q):
        """Rotate a 3d vector using quaternion of rotation. Returns rotated 3d vector."""
        assert v.shape == (3, )
        assert q.shape == (4, )
        v = cls.from_vector(v)
        return cls.rotate_quaternion(v, q)[1:]

    @classmethod
    def rotate_quaternion(cls, p, q):
        """Rotate a 4d quaternion p using a 4d quaternion of rotation q. Returns rotated 4d quaternion."""
        assert p.shape == (4, )
        assert q.shape == (4, )
        qp = cls.multi(q, p)
        p_ = cls.multi(qp, cls.inverse(q))
        return p_

    @classmethod
    def from_vector_angle(cls, rotation_axis_vector, rotation_angle_degrees):
        """Produce a quaternion of rotation given a rotation axis and angle."""
        assert rotation_axis_vector.shape == (3, )
        roation_angle_radians = rotation_angle_degrees / RADIANS_IN_DEGREES
        v = cls.normalize(rotation_axis_vector)
        q = np.asarray([
            np.cos(roation_angle_radians / 2),
            *(v * np.sin(roation_angle_radians / 2)),
        ])
        return q

    @classmethod
    def from_vector(cls, v):
        return np.asarray([0, *v])

    @classmethod
    def normalize(cls, q):
        return q / np.linalg.norm(q)

    @classmethod
    def norm_x(cls):
        return np.asarray([1, 0, 0])

    @classmethod
    def norm_y(cls):
        return np.asarray([0, 1, 0])

    @classmethod
    def norm_z(cls):
        return np.asarray([0, 0, 1])

    @classmethod
    def inverse(cls, q):
        return q * (1, -1, -1, -1)

    @classmethod
    def get_rotated_axes(cls, q):
        q_ = cls.inverse(q)
        return [
            cls.rotate_vector(cls.norm_x(), q_),
            cls.rotate_vector(cls.norm_y(), q_),
            cls.rotate_vector(cls.norm_z(), q_),
        ]

    @classmethod
    def multiply_many_one(cls, qr, qs):
        """Multiply many quaternions by a single quaternion. Returns resulting quaternions."""
        wr = qr[:, 0]
        ws = qs[0]
        vr = qr[:, 1:]
        vs = qs[1:]
        d = np.dot(vr, vs)
        qw = wr * ws - d
        crs = np.cross(vr, vs)
        part1 = vr * ws
        part2 = vs * wr[:, None]
        qv = part1 + part2 + crs
        r = np.concatenate((qw[:, None], qv), axis=-1)
        return r

    @classmethod
    def multiply_one_many(cls, qr, qs):
        """Multiply a single quaternion by many. Returns resulting quaternions."""
        wr = qr[0]
        ws = qs[:, 0]
        vr = qr[1:]
        vs = qs[:, 1:]
        d = np.dot(vs, vr)
        qw = wr * ws - d
        crs = np.cross(vr, vs)
        part1 = vr * ws[:, None]
        part2 = vs * wr
        qv = part1 + part2 + crs
        r = np.concatenate((qw[:, None], qv), axis=-1)
        return r

    @classmethod
    def multi(cls, qr, qs):
        """Multiply two quaternions. Returns resulting quaternion."""
        wr = qr[0]
        ws = qs[0]
        vr = qr[1:]
        vs = qs[1:]
        qw = wr * ws - np.dot(vr, vs)
        qv = vr * ws + vs * wr + np.cross(vr, vs)
        r = np.asarray([qw, *qv])
        return r

    @classmethod
    def ln(cls, q):
        w = q[0]
        v = q[1:]
        r = math.sqrt((v * v).sum())
        t = math.atan2(r, w) / r if r > EPSILON else 0
        w_ = math.log((q * q).sum()) * 0.5
        v_ = v * t
        return np.asarray([w_, *v])

    @classmethod
    def exp(cls, q):
        w = q[0]
        v = q[1:]
        r = math.sqrt((v * v).sum())
        et = math.exp(w)
        s = et * math.sin(r) / r if r > EPSILON else 0
        w_ = et * math.cos(r)
        v_ = v * s
        return np.asarray([w_, *v_])

    @classmethod
    def pow(cls, q, n):
        return cls.exp(cls.ln(q) * n)
