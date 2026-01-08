from xml.etree.ElementTree import fromstring

from epub_translator.epub.math import xml_to_latex


def test_fraction_with_subscript():
    """测试你的 EPUB 文件中实际的例子：分数 + 下标 + 箭头"""
    mathml = """<math display="inline">
      <mrow>
        <mrow>
          <mfrac>
            <mrow>
              <msub>
                <mi>S</mi>
                <mrow>
                  <mn>1</mn>
                </mrow>
              </msub>
            </mrow>
            <mrow>
              <mi>S</mi>
            </mrow>
          </mfrac>
        </mrow>
        <mo>→</mo>
        <mrow>
          <mfrac>
            <mrow>
              <msub>
                <mi>S</mi>
                <mrow>
                  <mn>2</mn>
                </mrow>
              </msub>
            </mrow>
            <mrow>
              <mi>a</mi>
            </mrow>
          </mfrac>
        </mrow>
      </mrow>
    </math>"""

    element = fromstring(mathml)
    result = xml_to_latex(element)

    assert result == r"\frac{S_{1}}{S}\rightarrow\frac{S_{2}}{a}"


def test_simple_fraction():
    """简单分数"""
    mathml = """<math>
        <mfrac>
            <mi>a</mi>
            <mi>b</mi>
        </mfrac>
    </math>"""

    element = fromstring(mathml)
    result = xml_to_latex(element)

    assert result == r"\frac{a}{b}"


def test_subscript():
    """下标"""
    mathml = """<math>
        <msub>
            <mi>x</mi>
            <mn>2</mn>
        </msub>
    </math>"""

    element = fromstring(mathml)
    result = xml_to_latex(element)

    assert result == r"x_{2}"


def test_superscript():
    """上标"""
    mathml = """<math>
        <msup>
            <mi>x</mi>
            <mn>2</mn>
        </msup>
    </math>"""

    element = fromstring(mathml)
    result = xml_to_latex(element)

    assert result == r"x^{2}"


def test_sqrt():
    """平方根"""
    mathml = """<math>
        <msqrt>
            <mi>x</mi>
        </msqrt>
    </math>"""

    element = fromstring(mathml)
    result = xml_to_latex(element)

    assert result == r"\sqrt{x}"


def test_nested_fraction():
    """嵌套分数"""
    mathml = """<math>
        <mfrac>
            <mfrac>
                <mi>a</mi>
                <mi>b</mi>
            </mfrac>
            <mi>c</mi>
        </mfrac>
    </math>"""

    element = fromstring(mathml)
    result = xml_to_latex(element)

    assert result == r"\frac{\frac{a}{b}}{c}"


def test_operator_mapping():
    """运算符映射"""
    mathml = """<math>
        <mrow>
            <mi>a</mi>
            <mo>×</mo>
            <mi>b</mi>
            <mo>≤</mo>
            <mi>c</mi>
        </mrow>
    </math>"""

    element = fromstring(mathml)
    result = xml_to_latex(element)

    assert result == r"a\timesb\leqc"


def test_greek_letters():
    """希腊字母"""
    mathml = """<math>
        <mrow>
            <mo>π</mo>
            <mo>=</mo>
            <mn>3.14</mn>
        </mrow>
    </math>"""

    element = fromstring(mathml)
    result = xml_to_latex(element)

    assert result == r"\pi=3.14"


def test_non_math_element():
    """非 math 元素应该返回空字符串"""
    xml = """<div>not a math element</div>"""
    element = fromstring(xml)
    result = xml_to_latex(element)

    assert result == ""
