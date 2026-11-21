# Licenses and trademarks

This page identifies the licenses and policies relevant to this repository. It is an engineering summary, not a legal opinion. Check the exact software and dependencies you distribute, including any source code copied from other projects.

## This SDK

The repository provides its own code under the [MIT License](../LICENSE). The MIT license applies only to material that the contributors have the right to license. It does not replace the licenses of external dependencies. The origin of the initial supplied project archive has not been independently audited for copied third-party code.

## CatBoost and ClickHouse software

The [CatBoost repository license](https://github.com/catboost/catboost/blob/master/LICENSE) and the [ClickHouse repository license](https://github.com/ClickHouse/ClickHouse/blob/master/LICENSE) state Apache License 2.0 for their respective projects. The SDK declares CatBoost as a Python dependency. It uses a separately installed ClickHouse server. The generated UDF ZIP contains its worker, model, manifest, and a dependency requirement; it does not contain the CatBoost package or a ClickHouse binary.

Apache 2.0 permits use, modification, and distribution subject to its terms. When distributing Apache-licensed code or binaries, review [section 4 of Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0), including the license copy, notices, and modified-file requirements. Preserve applicable `NOTICE` content when the distributed work includes it. A dependency installation can bring additional packages with their own licenses. Review the exact artifacts and transitive dependencies if you redistribute them.

ClickHouse Cloud is a separate hosted service with its own [service terms](https://clickhouse.com/legal/clickhouse-cloud-addendum). This repository does not deploy to Cloud, and the bundle has not been tested there.

## Product names and trademarks

The Apache license does not grant general trademark rights. This SDK is independent and is not endorsed or supported by ClickHouse, Inc. or the CatBoost project.

The current project and package names contain `ClickHouse`. The [ClickHouse trademark policy](https://clickhouse.com/legal/trademark-policy) restricts use of the mark in product names and describes conditions for compatibility statements. Review that policy before public release. Consider a distinct project name and seek permission or legal advice if needed. The policy also specifies a trademark legend for permitted uses.

This review does not establish permission to use the CatBoost name as a product name. Check the applicable trademark rules separately before selecting a public name.

ClickHouse is a registered trademark of ClickHouse, Inc. https://clickhouse.com/
