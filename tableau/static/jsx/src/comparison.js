/** @jsx React.DOM */
var HyperLinkValue = React.createClass({
    getDefaultProps: function() {
        return {'shortenUrls': false};
    },
    render: function() {
        var value = this.props.value;
        if (this.props.shortenUrls) {
            return (<a href={value} title={value}>
                {$.url(value).attr('host')}</a>);
        } else {
            return (<a href={value}>{value}</a>);
        }
    }
});

var FieldValue = React.createClass({
    getInitialState: function() {
        return {'collapsed': true};
    },
    getDefaultProps: function() {
        return {'shortenUrls': true,
        'cutoff': 75,
        'id': Math.random().toString(36).slice(2) };
    },
    handleClick: function() {
        this.setState({collapsed: !this.state.collapsed});
        this.preventDefault();
    },
    render: function() {
        // not specified is just a dash
        if (this.props.value === undefined) {
            return (<td className="value not-available">-</td>);
        }

        // check, if we have an URL ...
        if (_.str.startsWith(this.props.value, "http")) {
            return (<td className="value">
                <HyperLinkValue value={this.props.value}
                shortenUrls={this.props.shortenUrls} /></td>);
        }

        var isbnPattern = /(.*?)([0-9X-]{10,25})(.*)/;

        // make ISBNs clickable (worldcat)
        if (this.props.value.match(isbnPattern)) {
            var match = isbnPattern.exec(this.props.value);
            if (match[2].length >= 13 && match[2].substring(0, 3) !== "978") {
                // prevent long digit strings to be turned into links
                // TODO: make a better regex!
            } else {
                return (<td className="value">{match[1]}
                        <a href={"http://www.worldcat.org/search?q=" + match[2]}>{match[2]}</a>
                        {match[3]}</td>);
            }
        }

        if (this.props.value.length > this.props.cutoff) {
            if (this.state.collapsed) {
                var value = _.str.prune(this.props.value,
                    this.props.cutoff, "");
                var remainingChars = this.props.value.length -
                this.props.cutoff;
                return (<td className="value">{value} &mdash;
                    <a onClick={this.handleClick}
                    href={"#" + this.props.id}>
                    <span className="expand-value">
                    {remainingChars} more...</span></a></td>);
            } else {
                return (<td className="value">{this.props.value}
                    &mdash; <a onClick={this.handleClick}
                    href={"#" + this.props.id}>Collapse</a></td>);
            }

        } else {
            return (<td className="value">{this.props.value}</td>);
        }

    }
});

var FieldRow = React.createClass({
    getDefaultProps: function() {
        omitTag: true
    },
    render: function() {
        var tag = this.props.tag;
        if (this.props.omitTag) { tag = ""; }
        var rowIsComparable = (this.props.leftValue !== undefined &&
            this.props.rightValue !== undefined);
        var comparableClass = rowIsComparable ? "comparable" : "incomparable";
        return (<tr className="field" className={comparableClass}>
            <td className="tag">{tag}</td>
            <td>{this.props.code}</td>
            <FieldValue value={this.props.leftValue} />
            <FieldValue value={this.props.rightValue} />
            </tr>);
    }
});

var ComparisonTable = React.createClass({
    getDefaultProps: function() {
        return {defaultTags: {
        "001": [],
        "020": ["a", "9"],
        "100": [],
        "245": ["a", "b", "c"],
        // "250": ["a"],
        // "260": ["a", "b", "c"],
        // "300": ["a"],
        // "500": ["a"],
        // "655": ["a"],
        "700": [],
        "776": [], // TODO: fix omitted non-first single tag ...
        // "935": ["a", "b"]
    }};
    },
    getInitialState: function() {
        return {expanded: false};
    },
    getAllDefinedTags: function() {
        var keys = _.union(Object.keys(this.props.left['record']['content']),
            Object.keys(this.props.right['record']['content']));
        dict = {}
        keys.forEach(function(key) { dict[key] = []; });
        return dict;
    },
    handleClick: function() {
        this.setState({expanded: !this.state.expanded});
    },
    render: function() {
        $this = this;
        var rows = [];
        var tags = this.state.expanded ? this.getAllDefinedTags() :
        this.props.defaultTags;

        Object.keys(tags).sort().forEach(function(tag, i) {

            leftValue = $this.props.left['record']['content'][tag] ||
            (tag < "010" ? "-" : []);
            rightValue = $this.props.right['record']['content'][tag] ||
            (tag < "010" ? "-" : []);

            if (tag < "010") {
                // simple control field
                rows.push(<FieldRow tag={tag} omitTag={false} code=""
                    leftValue={leftValue} rightValue={rightValue} />);
            } else {
                // complicated data field
                // maximum number of repeated fields, e.g. 2 x "020" etc.
                var max = Math.max(leftValue.length, rightValue.length);

                for (var i = 0; i < max; i++) {
                    leftValue[i] = leftValue[i] || {};
                    rightValue[i] = rightValue[i] || {};

                    // subfield codes
                    leftCodes = Object.keys(leftValue[i]);
                    rightCodes = Object.keys(rightValue[i]);
                    var codes = _.union(leftCodes, rightCodes);

                    // ignore indicator for now
                    codes = _.without(codes, "ind1", "ind2");

                    // for each subfield code that appears in either doc
                    for (var j = 0; j < codes.length; j++) {
                        var code = codes[j];

                        if (tags[tag].length == 0 ||
                            _.contains(tags[tag], code)) {
                            // get the subfield value ...
                        var leftSubfieldValue = leftValue[i][code];
                        var rightSubfieldValue = rightValue[i][code];

                            // .. normalize to an array
                            // TODO: make arrays the default down the chain!
                            if (!_.isArray(leftSubfieldValue)) {
                                leftSubfieldValue = [leftSubfieldValue];
                            }
                            if (!_.isArray(rightSubfieldValue)) {
                                rightSubfieldValue = [rightSubfieldValue];
                            }

                            // typical subfield value count is 1,
                            // but repeated subfield values have been
                            // spotted in 100.a, 936.k, ...
                            maxSubfieldValueCount = Math.max(
                                leftSubfieldValue.length,
                                rightSubfieldValue.length);

                            for (var k = 0; k < maxSubfieldValueCount; k++) {
                                rows.push(<FieldRow tag={tag}
                                    omitTag={k > 0 || j > 0}
                                    code={code}
                                    leftValue={leftSubfieldValue[k]}
                                    rightValue={rightSubfieldValue[k]} />);
                            }
                        }
                    }
                }
            }
        });
var linkText = this.state.expanded ? "Fewer Details" : "More Details";
rows.push(<tr>
    <td colSpan="4"><a onClick={this.handleClick}
    href="#">{linkText}</a> </td></tr>);
return (<table><tbody>{rows}</tbody></table>);
}
});

var Comparison = React.createClass({
    getInitialState: function() {
        return {left: {}, right: {}, };
    },
    getDefaultProps: function() {
        return {'base': 'http://localhost:5000/doc'}
    },
    componentWillMount: function() {
        var $this = this;
        var leftParts = this.props.left.split("://");
        var leftIndex = leftParts[0];
        var leftId = leftParts[1];
        var leftUrl = this.props.base + "/" + leftIndex + "/" + leftId;

        var rightParts = this.props.right.split("://");
        var rightIndex = rightParts[0];
        var rightId = rightParts[1];
        var rightUrl = this.props.base + "/" + rightIndex + "/" + rightId;

        $.ajax({
            url: leftUrl,
            datatype: 'json',
            success: function(data) {
                $this.setState({left: {index: leftIndex, id: leftId,
                    record: data}});
            },
            error: function(xhr, status, err) {
                console.error(xhr, status, err);
            }
        });

        $.ajax({
            url: rightUrl,
            datatype: 'json',
            success: function(data) {
                $this.setState({right: {index: rightIndex, id: rightId,
                    record: data}});
            },
            error: function(xhr, status, err) {
                console.error(xhr, status, err);
            }
        });
    },
    render: function() {
        if (_.isEmpty(this.state.left) && _.isEmpty(this.state.right)) {
            return (<div><p><img src="{{ url_for('static', filename='images/ajax-loader.gif')}}" /> &ndash; Loading two documents...</p></div>);
        } else if (_.isEmpty(this.state.left) || _.isEmpty(this.state.right)) {
            return (<div><p><img src="{{ url_for('static', filename='images/ajax-loader.gif')}}" /> &ndash; Loaded one documents, one to go...</p></div>);
        } else {
            return (<div><ComparisonTable left={this.state.left}
                right={this.state.right} /></div>);
        }
    }
});

React.renderComponent(
    <Comparison base="{{ payload.base }}"
    left="{{ payload.left.index }}://{{ payload.left.id }}"
    right="{{ payload.right.index }}://{{ payload.right.id }}" />,
    document.getElementById("comparison"));
